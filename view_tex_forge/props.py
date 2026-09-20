import bpy
from bpy.props import (
    BoolProperty, EnumProperty, PointerProperty, StringProperty, FloatProperty,
    FloatVectorProperty, IntProperty,
)
from .preview import preview_settings_update



def comfyui_server_url_update(self, context):
    try:
        from .comfyui_client import request_connection_check
        self.comfyui_connection_status = 'UNKNOWN'
        self.comfyui_connection_error = ''
        request_connection_check()
    except Exception:
        pass



def comfyui_workflow_update(self, context):
    self.comfyui_workflow_status = 'UNKNOWN'
    self.comfyui_workflow_error = ''
    self.comfyui_workflow_signature = ''


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

    comfyui_server_url: StringProperty(
        name="Server URL",
        description="Base URL of the ComfyUI server",
        default="http://127.0.0.1:8188",
        update=comfyui_server_url_update,
    )

    comfyui_connection_status: EnumProperty(
        name="Connection Status",
        items=[
            ('UNKNOWN', 'Unknown', 'Connection has not been checked yet'),
            ('CHECKING', 'Checking', 'Checking ComfyUI connection'),
            ('CONNECTED', 'Connected', 'Connected to ComfyUI'),
            ('FAILED', 'Connection Failed', 'Could not connect to ComfyUI'),
        ],
        default='UNKNOWN',
        options={'SKIP_SAVE'},
    )

    comfyui_connection_error: StringProperty(
        name="Connection Error",
        default="",
        options={'SKIP_SAVE'},
    )

    comfyui_workflow_mode: EnumProperty(
        name="Workflow",
        items=[
            ('BUILTIN', 'Built-in', 'Use the ViewTexForge bundled ComfyUI workflow'),
            ('CUSTOM', 'Custom', 'Use a custom API-format workflow JSON'),
        ],
        default='BUILTIN',
        update=comfyui_workflow_update,
    )

    comfyui_workflow_path: StringProperty(
        name="Custom Workflow JSON",
        description="Optional custom ComfyUI API-format workflow JSON",
        subtype='FILE_PATH',
        default="",
        update=comfyui_workflow_update,
    )

    comfyui_workflow_status: EnumProperty(
        name="Workflow Status",
        items=[
            ('UNKNOWN', 'Unknown', 'Workflow has not been validated yet'),
            ('CHECKING', 'Checking', 'Validating workflow contract'),
            ('VALID', 'Valid', 'Workflow contract is valid'),
            ('ERROR', 'Workflow Error', 'Workflow contract validation failed'),
        ],
        default='UNKNOWN',
        options={'SKIP_SAVE'},
    )

    comfyui_workflow_error: StringProperty(
        name="Workflow Error",
        default="",
        options={'SKIP_SAVE'},
    )

    comfyui_workflow_signature: StringProperty(
        name="Workflow Signature",
        default="",
        options={'SKIP_SAVE'},
    )

    comfyui_reference_image: StringProperty(
        name="Reference Image",
        description="Single reference image shared by all camera views",
        subtype='FILE_PATH',
        default="",
    )

    comfyui_seed_mode: EnumProperty(
        name="Seed Mode",
        items=[
            ('FIXED', 'Fixed', 'Use the base seed as-is'),
            ('INCREMENT', 'Increment', 'Increment the base seed for each workflow batch'),
            ('RANDOM', 'Random', 'Resolve a random seed in ViewTexForge before submission'),
        ],
        default='FIXED',
    )

    comfyui_base_seed: IntProperty(
        name="Base Seed",
        description="Base seed resolved by ViewTexForge and passed to ComfyUI",
        default=18,
        min=0,
        max=2147483647,
    )

    comfyui_is_running: BoolProperty(
        name="ComfyUI Running",
        default=False,
        options={'SKIP_SAVE'},
    )

    comfyui_progress: FloatProperty(
        name="Progress",
        subtype='PERCENTAGE',
        default=0.0,
        min=0.0,
        max=100.0,
        options={'SKIP_SAVE'},
    )

    comfyui_status_text: StringProperty(
        name="Generation Status",
        default="Idle",
        options={'SKIP_SAVE'},
    )

    comfyui_prompt_id: StringProperty(
        name="Prompt ID",
        default="",
        options={'SKIP_SAVE'},
    )

    comfyui_input_mapping_json: StringProperty(
        name="Input Mapping",
        default="",
        options={'SKIP_SAVE'},
    )

    comfyui_resolved_seed: IntProperty(
        name="Resolved Seed",
        default=0,
        min=0,
        max=2147483647,
        options={'SKIP_SAVE'},
    )

