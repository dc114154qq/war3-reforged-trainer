"""Request-scoped diagnostics; observing a report never replays an operation."""
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from collections.abc import Mapping
from pathlib import Path
import hashlib
import sys
import traceback
import uuid

_ACTIVE_TRACE = ContextVar('war3_operation_trace', default=None)
DIAGNOSTIC_REVISION = 'ability-instances-item-carrier-v3-20261012'


def _plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
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
    source_inputs=('operation_trace.py','backpack_interface.py','facade_extensions.py')
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

    def summary(self):
        return dict(operation_id=self.operation_id, diagnostic_revision=DIAGNOSTIC_REVISION,
                    log_path=self.log_path, log_errors=list(self.log_errors),
                    phase=self.phase, native_execution_reports=self.execution_count,
                    click_evidence='not_collected', actual_open_effect_verified=False)

    def record(self, phase, **values):
        self.phase = phase
        if self.logger is None:
            return
        try:
            self.logger.log('backpack_phase', operation_id=self.operation_id,
                            phase=phase, payload=_plain(values))
            # The legacy logger can lose its file after an I/O error.
            if getattr(self.logger, '_files', None) == []:
                raise OSError('No diagnostic file remains writable')
        except Exception as exc:
            if len(self.log_errors) < 8:
                self.log_errors.append(repr(exc))

    def __enter__(self):
        self.token = _ACTIVE_TRACE.set(self)
        try:
            self.logger = self.logger_factory(
                getattr(self.host, 'pid', None), prefix=self.prefix,
                target_hwnd=getattr(self.host, 'hwnd', 0))
            self.log_path = str(self.logger.archive_path)
        except Exception as exc:
            self.log_errors.append(repr(exc))
        session = getattr(self.host, '_game_session', None)
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
                            session_report=getattr(exc, 'session_report', None))
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
            if self.result_summary is not None:
                self.result_summary.update(self.summary())
            if exc is not None:
                exc.report['operation_trace'] = self.summary()
        finally:
            _ACTIVE_TRACE.reset(self.token)
        # Logging failure preserves the original outcome; it never retries a write.
        return False


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


def record_engine_execution(engine, report):
    trace = _ACTIVE_TRACE.get()
    if trace is None or (trace.engine is not None and trace.engine is not engine):
        return
    try:
        trace.execution_count += 1
        report['operation_id'] = trace.operation_id
        report['parent_phase'] = trace.phase
        trace.record(trace.phase, native_execution_index=trace.execution_count,
                     execution_report=deepcopy(report))
    except Exception as exc:
        if len(trace.log_errors) < 8:
            trace.log_errors.append(repr(exc))
