import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty


def camera_poll(self, obj):
    return obj is not None and obj.type == 'CAMERA'


class VIEWTEXFORGE_PG_Settings(bpy.types.PropertyGroup):
    target_mode: EnumProperty(
        name="Render Target",
        items=[
            ('ALL_RENDERABLE', 'All Renderable', 'Use all renderable objects in the scene'),
            ('SELECTED_ONLY', 'Selected Only', 'Use only selected objects'),
        ],
        default='ALL_RENDERABLE',
    )

    output_clay: BoolProperty(
        name="Clay",
        description="Output clay viewport image (Solid + MatCap)",
        default=True,
    )
    output_normal: BoolProperty(
        name="Normal",
        description="Output normal image",
        default=True,
    )
    output_depth: BoolProperty(
        name="Depth",
        description="Output depth image",
        default=True,
    )

    camera_mode: EnumProperty(
        name="Camera",
        items=[
            ('VIEWPORT', 'Viewport Camera', 'Use the current 3D viewport camera/view'),
            ('AUTO4', 'Auto 4 Cameras', 'Create front/back/left/right cameras automatically'),
            ('SPECIFIED', 'Specified Camera', 'Use a specified camera object'),
        ],
        default='AUTO4',
    )

    specified_camera: PointerProperty(
        name="Specified Camera",
        type=bpy.types.Object,
        poll=camera_poll,
    )

    output_dir: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        default="//ai_texture_capture",
    )
