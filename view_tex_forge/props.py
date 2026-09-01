import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from .preview import preview_settings_update


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

    output_mask: BoolProperty(
        name="Mask",
        description="Output foreground mask image",
        default=True,
    )

    render_size_preset: EnumProperty(
        name="Qwen Size",
        description="Output size preset for Qwen image workflows",
        items=[
            ('1024', '1024 x 1024 (Recommended)', 'Recommended standard size for Qwen workflows'),
            ('1280', '1280 x 1280 (Balanced)', 'A balanced higher-detail square size'),
            ('1536', '1536 x 1536 (Detail)', 'Higher detail, heavier processing'),
        ],
        default='1024',
        update=preview_settings_update,
    )

    camera_mode: EnumProperty(
        name="Camera",
        items=[
            ('VIEWPORT', 'Viewport Camera', 'Use the current 3D viewport camera/view'),
            ('AUTO4', 'Auto 4 Cameras', 'Create front/back/left/right cameras automatically'),
            ('SPECIFIED', 'Specified Camera', 'Use a specified camera object'),
        ],
        default='AUTO4',
        update=preview_settings_update,
    )

    specified_camera: PointerProperty(
        name="Specified Camera",
        type=bpy.types.Object,
        poll=camera_poll,
    )

    preview_mode: BoolProperty(
        name="Viewport Preview",
        description="Show an overlay frame for the selected output size when using Viewport Camera mode",
        default=False,
        update=preview_settings_update,
    )

    output_dir: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        default="//ai_texture_capture",
    )
