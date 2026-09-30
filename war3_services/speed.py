"""Process-wide speed service; retained hooks belong to GameSession resources."""
from pathlib import Path


def toggle_scaled_speed(trainer,factor=2):
    from war3_speed_clock_backend import SpeedClockBackend, encode_speed_factor
    encoded=encode_speed_factor(factor)
    engine=trainer._engine_instance_24268()
    session=engine.session
    with session.lock:
        from war3_capabilities import CapabilitySet
        CapabilitySet(session.profile).require('speed_clock')
        session.require_write()
        clock=session.resources.get('speed_clock')
        if clock is None or not clock.handle:
            root=Path(__file__).resolve().parent.parent
            candidates=(engine.image.parent/'war3_speed_clock.dll',
                        root/'build/speed-clock-runtime/war3_speed_clock.dll',
                        root/'tools/war3_speed_clock.dll')
            image=next((path for path in candidates if path.is_file()),None)
            if image is None:raise RuntimeError('Missing speed clock module')
            clock=SpeedClockBackend(engine,image)
            clock.attach()
        current=clock.query()
        if clock.saved_rate is not None:
            result=clock.set_rate(clock.saved_rate)
            clock.saved_rate=None
            return dict(result,accelerated=False)
        if encoded==round(current['rate']*1000):
            return dict(current,accelerated=False,unchanged=True)
        result=clock.set_rate(factor)
        clock.saved_rate=current['rate']
        return dict(result,accelerated=True)
