"""Request-scoped diagnostics; observing a report never replays an operation."""
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from collections.abc import Mapping
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import time
import traceback
import uuid

_ACTIVE_TRACE = ContextVar('war3_operation_trace', default=None)
DIAGNOSTIC_REVISION = 'native-call-journal-v4-20261012'


def active_trace():
    return _ACTIVE_TRACE.get()


def record_operation_phase(engine, phase, **values):
    trace = active_trace()
    if trace is not None and (trace.engine is None or trace.engine is engine):
        trace.record(phase, **values)


def _plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return dict(nonfinite_float=repr(value))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _artifact(path):
    path = Path(path)
    result = {'path': str(path)}
    try:
        result['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        result['hash_error'] = repr(exc)
    return result


class BackpackTrace:
    prefix='backpack'
    event_name='backpack_phase'
    source_inputs=('operation_trace.py','backpack_interface.py','backpack_carrier.py','facade_extensions.py')
    def __init__(self, host, logger_factory, request):
        self.host, self.logger_factory, self.request = host, logger_factory, request
        self.operation_id = uuid.uuid4().hex
        self.phase = 'start'
        self.engine = None
        self.logger = None
        self.log_path = None
        self.log_errors = []
        self.execution_count = 0
        self.result_summary = None
        self.structured_file = None
        self.structured_path = None
        self.event_sequence = 0
        self.started = time.perf_counter()
        self.last_native_execution = None

    def summary(self):
        return dict(operation_id=self.operation_id, diagnostic_revision=DIAGNOSTIC_REVISION,
                    log_path=self.log_path, log_errors=list(self.log_errors),
                    phase=self.phase, native_execution_reports=self.execution_count,
                    structured_log_path=self.structured_path, event_count=self.event_sequence,
                    last_native_execution=self.last_native_execution,
                    click_evidence='not_collected', actual_open_effect_verified=False)

    def record(self, phase, **values):
        self.phase = phase
        if self.logger is None:
            return
        self.event_sequence += 1
        try:
            plain = _plain(values)
        except Exception as exc:
            if len(self.log_errors)<8:self.log_errors.append('serialization: '+repr(exc))
            return
        try:
            self.logger.log(self.event_name, operation_id=self.operation_id,
                            phase=phase, sequence=self.event_sequence,
                            payload=plain)
            if getattr(self.logger, '_files', None) == []:
                raise OSError('No diagnostic file remains writable')
        except Exception as exc:
            if len(self.log_errors)<8:self.log_errors.append('text_log: '+repr(exc))
        try:
            if self.structured_file is not None:
                row=dict(schema=4,operation_id=self.operation_id,sequence=self.event_sequence,
                         elapsed_ms=(time.perf_counter()-self.started)*1000,
                         phase=phase,payload=plain)
                self.structured_file.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
                self.structured_file.flush()
        except Exception as exc:
            if len(self.log_errors) < 8:
                self.log_errors.append('structured_log: '+repr(exc))

    def emit(self, phase, **values):
        previous=self.phase
        try:self.record(phase,**values)
        finally:self.phase=previous

    def checkpoint(self):
        """Persist the dispatch boundary before a game mutation can start."""
        if self.structured_file is not None:
            try:os.fsync(self.structured_file.fileno())
            except OSError as exc:
                if len(self.log_errors)<8:self.log_errors.append(repr(exc))

    def __enter__(self):
        self.token = _ACTIVE_TRACE.set(self)
        try:
            self.logger = self.logger_factory(
                getattr(self.host, 'pid', None), prefix=self.prefix,
                target_hwnd=getattr(self.host, 'hwnd', 0))
            self.log_path = str(self.logger.archive_path)
            path=Path(self.log_path).with_suffix('.jsonl')
            try:
                self.structured_file=path.open('x',encoding='utf-8',buffering=1)
                self.structured_path=str(path)
            except OSError as exc:self.log_errors.append('structured_log: '+repr(exc))
        except Exception as exc:
            self.log_errors.append(repr(exc))
        session = getattr(self.host, '_game_session', None) or getattr(self.host,'session',None)
        identity = getattr(session, 'identity', None)
        profile = getattr(session, 'profile', None)
        data = getattr(profile, 'data', {})
        adapter = ({key: data.get(key) for key in
                    ('id', 'game_version', 'adapter_version', 'schema_version', 'bridge_profile_version')}
                   if isinstance(data, Mapping) else {})
        artifacts = {'kind': 'frozen_executable' if getattr(sys, 'frozen', False) else 'source'}
        if getattr(sys, 'frozen', False):
            artifacts['executable'] = _artifact(sys.executable)
        else:
            artifacts['inputs'] = [_artifact(Path(__file__).with_name(name)) for name in self.source_inputs]
        self.record('start', request=self.request, session_identity=identity,
                    session_epoch=getattr(session, 'epoch', None), adapter=adapter,
                    trainer_artifact=artifacts, diagnostic_revision=DIAGNOSTIC_REVISION,
                    observation_contract=dict(native_calls='original calls observed once; no diagnostic game writes',
                        native_journal='copied after callback returns; interrupted dispatch may have no call records',
                        object_definition_registration='not inferred from native registration or level zero',
                        native_call_capacity=1024,overflow='explicit count and final call retained'),
                    click_evidence='not_collected', actual_open_effect_verified=False)
        return self

    def finish(self, snapshot):
        self.record('complete', readback=snapshot,
                    component_readback_verified=True, actual_open_effect_verified=False)
        self.result_summary = self.summary()
        snapshot.setdefault('backpack_interface', {})['operation_trace'] = self.result_summary
        return snapshot

    def bind_engine(self, engine):
        self.engine = engine
        import struct
        from war3_hero_protocol import ABI
        image = getattr(engine, 'image', None)
        bridge = _artifact(image) if isinstance(image, (str, Path)) else {'identity': 'unavailable'}
        self.record('engine_context', bridge=bridge, expected_bridge_protocol=hex(struct.unpack_from('<I',ABI)[0]))

    def __exit__(self, kind, exc, tb):
        try:
            if exc is not None:
                failed_phase = self.phase
                self.record('failed', failed_phase=failed_phase, exception_type=type(exc).__name__,
                            exception=str(exc), traceback=''.join(traceback.format_exception(kind, exc, tb)),
                            execution_report=getattr(exc, 'report', None),
                            session_report=getattr(exc, 'session_report', None),
                            exception_chain=self._exception_chain(exc),
                            diagnostic_conclusion=dict(failure_location=failed_phase,
                                game_internal_rejection_cause_confirmed=False,
                                automatic_replay_performed=False))
                report = dict(getattr(exc, 'report', {}) or {})
                report['operation_trace'] = self.summary()
                exc.report = report
                if self.log_path:
                    exc.backpack_log_path = self.log_path
            if self.logger is not None:
                try:
                    self.logger.close()
                except Exception as error:
                    self.log_errors.append(repr(error))
            if self.structured_file is not None:
                try:
                    self.structured_file.write(json.dumps(dict(schema=4,event='trace_closed',
                        operation_id=self.operation_id,events=self.event_sequence,
                        outcome='failed' if exc is not None else 'returned',
                        log_errors=self.log_errors),ensure_ascii=False)+'\n')
                    self.structured_file.flush();os.fsync(self.structured_file.fileno())
                except OSError as error:self.log_errors.append(repr(error))
                finally:
                    try:self.structured_file.close()
                    except OSError as error:self.log_errors.append(repr(error))
            if self.result_summary is not None:
                self.result_summary.update(self.summary())
            if exc is not None:
                exc.report['operation_trace'] = self.summary()
        finally:
            _ACTIVE_TRACE.reset(self.token)
        # Logging failure preserves the original outcome; it never retries a write.
        return False

    @staticmethod
    def _exception_chain(exc):
        rows=[];seen=set()
        while exc is not None and id(exc) not in seen and len(rows)<16:
            seen.add(id(exc))
            rows.append(dict(type=type(exc).__name__,message=str(exc),
                             report=_plain(getattr(exc,'report',None))))
            exc=exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
        return dict(rows=rows,truncated=exc is not None)


class SkillTrace(BackpackTrace):
    prefix='skill'
    source_inputs=('operation_trace.py','facade_abilities.py','effect_lifetime.py')

    def summary(self):
        result=super().summary()
        result.pop('click_evidence',None);result.pop('actual_open_effect_verified',None)
        result['actual_effect_verified']=False
        return result

    def finish(self,result):
        self.record('complete',readback=result,actual_effect_verified=False)
        self.result_summary=self.summary()
        result['operation_trace']=self.result_summary
        return result


class CloneTrace(SkillTrace):
    prefix='clone'
    event_name='clone_phase'
    source_inputs=('operation_trace.py','units.py','facade_native.py')

    def bind_engine(self, engine):
        self.engine=engine
        import struct
        from war3_clone_protocol import ABI
        from war3_clone_bound_protocol import ABI as BOUND_ABI
        from war3_clone_state_protocol import ABI as STATE_ABI
        image=getattr(engine,'image',None)
        self.record('engine_context',bridge=_artifact(image) if isinstance(image,(str,Path)) else {},
                    expected_bridge_protocol=hex(struct.unpack_from('<I', STATE_ABI if self.request.get('operation')=='clone_state' else BOUND_ABI if
                        self.request.get('operation')=='clone_bound' else ABI)[0]))


def record_engine_execution(engine, report):
    trace = _ACTIVE_TRACE.get()
    if trace is None or (trace.engine is not None and trace.engine is not engine):
        return
    try:
        trace.execution_count += 1
        report['operation_id'] = trace.operation_id
        report['parent_phase'] = trace.phase
        copied=deepcopy(report)
        journal=copied.get('native_call_journal')
        if journal is not None:
            calls=journal.pop('calls',[])
            copied['native_call_journal']=journal
            for call in calls:
                trace.emit('native_call',native_execution_index=trace.execution_count,call=call)
        trace.last_native_execution=dict(index=trace.execution_count,operation=report.get('operation'),
            ok=report.get('ok'),request=_plain(report.get('request')),
            verification=_plain(report.get('verification')),
            business_status=_plain(report.get('business_status')),
            native_call_journal=_plain(journal))
        trace.record(trace.phase, native_execution_index=trace.execution_count,
                     execution_report=copied)
        trace.checkpoint()
    except Exception as exc:
        if len(trace.log_errors) < 8:
            trace.log_errors.append(repr(exc))
