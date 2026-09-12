import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty, FloatProperty, FloatVectorProperty
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

    clay_render_mode: EnumProperty(
        name="Clay Render Mode",
        items=[
            ('SOLID', 'Solid Viewport', 'Output a Solid viewport clay image using MatCap'),
            ('LIT', 'Lit Clay Render', 'Output a gray clay render with lighting enabled'),
        ],
        default='SOLID',
    )

    lighting_mode: EnumProperty(
        name="Lighting Mode",
        items=[
            ('EXISTING', 'Use Existing Lighting', 'Use the current scene lighting'),
            ('AUTO', 'Use Auto Lighting', 'Use an automatically generated 5-area-light rig'),
        ],
        default='EXISTING',
    )

    show_lighting_options: BoolProperty(
        name="Lighting Options",
        default=False,
    )

    light_power: FloatProperty(
        name="Light Power",
        description="Base power used for each auto-generated area light",
        default=1000.0,
        min=0.0,
        soft_max=100000.0,
    )

    light_exposure_front: FloatProperty(
        name="Front Exposure",
        description="Exposure used for the front auto light",
        default=6.0,
        soft_min=-10.0,
        soft_max=16.0,
    )

    light_exposure_back: FloatProperty(
        name="Back Exposure",
        description="Exposure used for the back auto light",
        default=6.0,
        soft_min=-10.0,
        soft_max=16.0,
    )

    light_exposure_left: FloatProperty(
        name="Left Exposure",
        description="Exposure used for the left auto light",
        default=6.0,
        soft_min=-10.0,
        soft_max=16.0,
    )

    light_exposure_right: FloatProperty(
        name="Right Exposure",
        description="Exposure used for the right auto light",
        default=6.0,
        soft_min=-10.0,
        soft_max=16.0,
    )

    light_exposure_top: FloatProperty(
        name="Top Exposure",
        description="Exposure used for the top auto light",
        default=8.0,
        soft_min=-10.0,
        soft_max=16.0,
    )

    light_normalize: BoolProperty(
        name="Normalize",
        description="Enable Normalize for each auto-generated area light",
        default=True,
    )

    light_use_shadow: BoolProperty(
        name="Cast Shadow",
        description="Enable shadow casting for each auto-generated area light",
        default=False,
    )

    light_color: FloatVectorProperty(
        name="Light Color",
        description="Color used for auto-generated lights",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )

    keep_auto_lights_debug: BoolProperty(
        name="Keep Auto Lights (Debug)",
        description="Keep the generated auto lights in the scene after capture for inspection",
        default=False,
    )

    camera_fit_margin: FloatProperty(
        name="Camera Margin",
        description="Framing margin for Auto 4 Cameras. Smaller values frame tighter.",
        default=1.05,
        min=1.0,
        soft_max=1.5,
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
