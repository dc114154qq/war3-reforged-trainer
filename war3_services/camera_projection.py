"""Warcraft screen projection, independent of process layout and transport.

The Warcraft camera is off-axis. Its native FOV is not the vertical angle
expected by a conventional tan(FOV/2) projection. The calibration and field
semantics here follow Antares' World2Screen 2.0 (September 19, 2026).
Source and executable-reference verification: docs/MOUSE_PROJECTION.md.
"""
from __future__ import annotations
import math

MODEL = 'warcraft-world2screen-2.0-20260919'


def mouse_plane_point(snapshot, width, height, scale=1.0, plane_z=None, *, diagnostics=None):
    report=diagnostics if diagnostics is not None else {}
    report.update(projection_model=MODEL, calibrated_against_game_render=False)
    def fail(reason):
        report['projection_failure']=reason
        error=RuntimeError('鼠标落点尚未确认，本次未执行传送：'+reason)
        error.report={'mouse_projection':report}
        raise error
    if not width>0 or not height>0 or not all(math.isfinite(float(v)) for v in (width,height)):
        fail('游戏视口尺寸无效')
    if not math.isfinite(scale) or not 0.5<=scale<=4:
        fail('鼠标 DPI 缩放无效')
    try:
        eye=tuple(map(float,snapshot['eye']))
        target=tuple(map(float,snapshot['target']))
        fields=tuple(map(float,snapshot['fields']))
        px,py=map(float,snapshot['screen'])
    except (KeyError,ValueError,TypeError):
        fail('相机快照不完整')
    if len(eye)!=3 or len(target)!=3 or len(fields)!=11:
        fail('相机快照缺少局部转向字段，请使用配套的新版本组件')
    if not all(math.isfinite(v) and abs(v)<=1_000_000 for v in (*eye,*target,*fields,px,py)):
        fail('相机或鼠标坐标无效')
    fov,attack,rotation=fields[3],fields[2],fields[5]
    if not 0.1<fov<math.pi-0.1:
        fail('游戏视野角读回无效')
    if any(abs(math.remainder(fields[i],2*math.pi))>1e-5 for i in (4,10)):
        # The reference does not implement global/local roll. A guessed roll
        # convention would silently move a unit to a different screen point.
        fail('当前相机有滚转，参考算法尚未确认这种视角的准确落点')
    space=snapshot.get('screen_space')
    if space=='normalized_u16' or space is None and (px>width*2 or py>height*2):
        render_width=render_height=65535.0
        space='normalized_u16'
    elif space in (None,'client_pixels'):
        render_width,render_height=width*scale,height*scale
        space='client_pixels'
    else:
        fail('鼠标坐标单位未识别')
    if not 0<=px<=render_width or not 0<=py<=render_height:
        fail('光标不在游戏视口内')
    # Warcraft UI coordinates have a vertical span of .6 and a horizontal
    # centre of .4 at every aspect ratio, including wide and portrait windows.
    screen_x=.4+(px/render_width-.5)*.6*(width/height)
    screen_y=.6*(1-py/render_height)
    centre_y=.42625-.1284*math.cos(attack)
    fov_scale=.0524*fov**3-.0283*fov**2+1.061*fov
    horizontal=(screen_x-.4)*fov_scale
    down=(centre_y-screen_y)*fov_scale
    # Native enum 8 = local pitch, 9 = local yaw. Enum 7 is near clip.
    pitch=attack+fields[8]
    yaw=rotation+fields[9]
    cp,sp,cy,sy=math.cos(pitch),math.sin(pitch),math.cos(yaw),math.sin(yaw)
    direction=(cp*cy+horizontal*sy+down*sp*cy,
               cp*sy-horizontal*cy+down*sp*sy,
               sp-down*cp)
    length=math.sqrt(sum(v*v for v in direction))
    direction=tuple(v/length for v in direction)
    report.update(screen_space=space,screen_pixels=(px,py),
                  render_size=(render_width,render_height),aspect_ratio=width/height,
                  ui_point=(screen_x,screen_y),principal_point=(.4,centre_y),
                  fov_radians=fov,fov_scale=fov_scale,angle_of_attack=attack,
                  local_pitch=fields[8],local_yaw=fields[9],ray_origin=eye,ray_direction=direction)
    if abs(direction[2])<=1e-9:
        fail('鼠标射线与地图平面平行')
    z=target[2] if plane_z is None else float(plane_z)
    if not math.isfinite(z) or abs(z)>1_000_000:
        fail('投影平面高度无效')
    distance=(z-eye[2])/direction[2]
    if not math.isfinite(distance) or distance<=0:
        fail('鼠标射线命中点位于相机后方')
    point=tuple(eye[i]+direction[i]*distance for i in range(2))
    if not all(math.isfinite(v) and abs(v)<=1_000_000 for v in point):
        fail('鼠标世界坐标超出范围')
    report['plane_point']=point
    return point
