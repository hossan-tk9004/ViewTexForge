import hashlib
import json
import mimetypes
import os
import queue
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import bpy


# ViewTexForge Workflow Contract. Nodes are discovered by _meta.title rather
# than by ComfyUI node IDs, so workflows can be edited/re-saved without
# breaking the integration as long as these contract titles are preserved.
WORKFLOW_CONTRACT = {
    "source_prefix": "ViewTexForge_input_SourceImage",
    "depth_prefix": "ViewTexForge_input_DepthImage",
    "mask_prefix": "ViewTexForge_input_MaskImage",
    "reference": "ViewTexForge_input_ReferenceImage",
    "positive_prompt": "ViewTexForge_input_PositivePrompt",
    "negative_prompt": "ViewTexForge_input_NegativePrompt",
    "seed": "ViewTexForge_input_Seed",
    "output_dir": "ViewTexForge_input_OutputDirName",
    "output_prefix": "ViewTexForge_input_OutputFilePrefix",
    "generated_output": "ViewTexForge_output_GeneratedImage",
}

WORKFLOW_EXPECTED_TYPES = {
    "reference": "LoadImage",
    "positive_prompt": "TextEncodeQwenImageEditPlus",
    "negative_prompt": "TextEncodeQwenImageEditPlus",
    "seed": "SeedNode",
    "output_dir": "PrimitiveString",
    "output_prefix": "PrimitiveString",
    "generated_output": "SaveImage",
}


def builtin_workflow_path():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "workflows",
        "Qwen_3DCharacterTexture_generator_ggfu.json",
    )


def resolve_workflow_path(settings):
    # ViewTexForge only runs its bundled, validated workflow.
    # Keeping this function centralizes the path and avoids exposing arbitrary
    # workflow selection in the UI.
    return builtin_workflow_path()


def _workflow_title_index(workflow):
    index = {}
    duplicates = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        title = str((node.get("_meta") or {}).get("title") or "").strip()
        if not title:
            continue
        if title in index:
            duplicates.setdefault(title, [index[title]]).append(str(node_id))
        else:
            index[title] = str(node_id)
    return index, duplicates


def _numbered_contract_nodes(title_index, prefix):
    found = []
    for title, node_id in title_index.items():
        if not title.startswith(prefix):
            continue
        suffix = title[len(prefix):]
        if not suffix.isdigit():
            continue
        found.append((int(suffix), node_id, title))
    found.sort(key=lambda item: item[0])
    return found


def validate_workflow(workflow, *, log_errors=True):
    errors = []
    if not isinstance(workflow, dict) or not workflow:
        errors.append("Workflow root must be a non-empty JSON object.")
        contract = None
    else:
        title_index, duplicates = _workflow_title_index(workflow)
        for title, ids in sorted(duplicates.items()):
            if title.startswith("ViewTexForge_"):
                errors.append(f"Duplicate contract title '{title}' on nodes {', '.join(ids)}.")

        contract = {"title_index": title_index}
        groups = {}
        for key, prefix in (
            ("source", WORKFLOW_CONTRACT["source_prefix"]),
            ("depth", WORKFLOW_CONTRACT["depth_prefix"]),
            ("mask", WORKFLOW_CONTRACT["mask_prefix"]),
        ):
            nodes = _numbered_contract_nodes(title_index, prefix)
            groups[key] = nodes
            if not nodes:
                errors.append(f"Missing nodes matching '{prefix}##'.")
                continue
            expected = list(range(1, len(nodes) + 1))
            actual = [item[0] for item in nodes]
            if actual != expected:
                errors.append(
                    f"{key.title()} image numbering must be contiguous from 01; found {actual}."
                )
            for _, node_id, title in nodes:
                node_type = workflow[node_id].get("class_type")
                if node_type != "LoadImage":
                    errors.append(
                        f"'{title}' must be class_type LoadImage, got {node_type!r}."
                    )
                elif "image" not in (workflow[node_id].get("inputs") or {}):
                    errors.append(f"'{title}' is missing inputs.image.")

        counts = {key: len(value) for key, value in groups.items()}
        if len(set(counts.values())) > 1:
            errors.append(
                "Source/Depth/Mask input counts must match: "
                + ", ".join(f"{key}={value}" for key, value in counts.items())
            )

        for key in (
            "reference", "positive_prompt", "negative_prompt", "seed",
            "output_dir", "output_prefix", "generated_output",
        ):
            title = WORKFLOW_CONTRACT[key]
            node_id = title_index.get(title)
            if node_id is None:
                errors.append(f"Missing required node title '{title}'.")
                continue
            expected_type = WORKFLOW_EXPECTED_TYPES[key]
            actual_type = workflow[node_id].get("class_type")
            if actual_type != expected_type:
                errors.append(
                    f"'{title}' must be class_type {expected_type}, got {actual_type!r}."
                )
                continue
            required_input_key = {
                "reference": "image",
                "positive_prompt": "prompt",
                "negative_prompt": "prompt",
                "seed": "seed",
                "output_dir": "value",
                "output_prefix": "value",
                "generated_output": "images",
            }[key]
            if required_input_key not in (workflow[node_id].get("inputs") or {}):
                errors.append(
                    f"'{title}' is missing inputs.{required_input_key}."
                )

        if not errors:
            contract.update({
                "source_nodes": [item[1] for item in groups["source"]],
                "depth_nodes": [item[1] for item in groups["depth"]],
                "mask_nodes": [item[1] for item in groups["mask"]],
                "reference_node": title_index[WORKFLOW_CONTRACT["reference"]],
                "positive_prompt_node": title_index[WORKFLOW_CONTRACT["positive_prompt"]],
                "negative_prompt_node": title_index[WORKFLOW_CONTRACT["negative_prompt"]],
                "seed_node": title_index[WORKFLOW_CONTRACT["seed"]],
                "output_dir_node": title_index[WORKFLOW_CONTRACT["output_dir"]],
                "output_prefix_node": title_index[WORKFLOW_CONTRACT["output_prefix"]],
                "save_node": title_index[WORKFLOW_CONTRACT["generated_output"]],
                "view_count": counts["source"],
            })

    if errors and log_errors:
        print("[ViewTexForge][Workflow Validation Error]")
        for error in errors:
            print(f"  - {error}")
    return not errors, errors, contract


def validate_workflow_file(path, *, log_errors=True):
    if not path or not os.path.isfile(path):
        errors = [f"Workflow JSON not found: {path or '<empty>'}"]
        if log_errors:
            print("[ViewTexForge][Workflow Validation Error]")
            print(f"  - {errors[0]}")
        return False, errors, None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            workflow = json.load(handle)
    except Exception as exc:
        errors = [f"Failed to read workflow JSON: {exc}"]
        if log_errors:
            print("[ViewTexForge][Workflow Validation Error]")
            print(f"  - {errors[0]}")
        return False, errors, None
    return validate_workflow(workflow, log_errors=log_errors)


_CONNECTION_LOCK = threading.Lock()
_CONNECTION_RESULT = None
_CONNECTION_IN_FLIGHT = False
_CONNECTION_FORCE = True
_CONNECTION_LAST_CHECK = 0.0
_CONNECTION_TIMER_REGISTERED = False
_CONNECTION_INTERVAL_SECONDS = 7.5


def _normalize_base_url(url):
    return (url or "").strip().rstrip("/")


def _http_json(url, method="GET", payload=None, timeout=5.0):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def check_connection(server_url, timeout=1.5):
    base = _normalize_base_url(server_url)
    if not base:
        return False, "Server URL is empty"
    try:
        # /system_stats is lightweight and available on standard ComfyUI servers.
        _http_json(f"{base}/system_stats", timeout=timeout)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def request_connection_check():
    global _CONNECTION_FORCE
    with _CONNECTION_LOCK:
        _CONNECTION_FORCE = True


def _connection_worker(server_url):
    global _CONNECTION_RESULT, _CONNECTION_IN_FLIGHT
    ok, error = check_connection(server_url)
    with _CONNECTION_LOCK:
        _CONNECTION_RESULT = (server_url, ok, error)
        _CONNECTION_IN_FLIGHT = False


def _connection_timer():
    global _CONNECTION_RESULT, _CONNECTION_IN_FLIGHT
    global _CONNECTION_FORCE, _CONNECTION_LAST_CHECK

    now = time.monotonic()

    with _CONNECTION_LOCK:
        result = _CONNECTION_RESULT
        _CONNECTION_RESULT = None

    if result is not None:
        checked_url, ok, error = result
        for scene in bpy.data.scenes:
            settings = getattr(scene, "viewtexforge_settings", None)
            if not settings:
                continue
            if _normalize_base_url(settings.comfyui_server_url) != _normalize_base_url(checked_url):
                continue
            settings.comfyui_connection_status = "CONNECTED" if ok else "FAILED"
            settings.comfyui_connection_error = error if not ok else ""

    with _CONNECTION_LOCK:
        due = _CONNECTION_FORCE or (now - _CONNECTION_LAST_CHECK >= _CONNECTION_INTERVAL_SECONDS)
        can_start = due and not _CONNECTION_IN_FLIGHT

    if can_start:
        scene = bpy.context.scene if bpy.context else None
        settings = getattr(scene, "viewtexforge_settings", None) if scene else None
        if settings:
            server_url = _normalize_base_url(settings.comfyui_server_url)
            settings.comfyui_connection_status = "CHECKING"
            with _CONNECTION_LOCK:
                _CONNECTION_FORCE = False
                _CONNECTION_LAST_CHECK = now
                _CONNECTION_IN_FLIGHT = True
            thread = threading.Thread(
                target=_connection_worker,
                args=(server_url,),
                daemon=True,
                name="ViewTexForge-ComfyUIConnection",
            )
            thread.start()

    # Workflow validation is intentionally local and lightweight. Validate when
    # settings change/start up, and keep detailed errors in the system console.
    for scene in bpy.data.scenes:
        settings = getattr(scene, "viewtexforge_settings", None)
        if not settings:
            continue
        path = resolve_workflow_path(settings)
        try:
            stat = os.stat(path)
            signature = f"{os.path.abspath(path)}|{stat.st_mtime_ns}|{stat.st_size}"
        except OSError:
            signature = f"{os.path.abspath(path) if path else '<empty>'}|missing"
        needs_validation = (
            settings.comfyui_workflow_status == "UNKNOWN"
            or settings.comfyui_workflow_signature != signature
        )
        if not needs_validation:
            continue
        settings.comfyui_workflow_status = "CHECKING"
        valid, errors, _ = validate_workflow_file(path, log_errors=True)
        settings.comfyui_workflow_signature = signature
        settings.comfyui_workflow_status = "VALID" if valid else "ERROR"
        settings.comfyui_workflow_error = "" if valid else (errors[0] if errors else "Unknown workflow error")

    return 0.5


def register_connection_monitor():
    global _CONNECTION_TIMER_REGISTERED
    if _CONNECTION_TIMER_REGISTERED:
        return
    _CONNECTION_TIMER_REGISTERED = True
    request_connection_check()
    bpy.app.timers.register(_connection_timer, first_interval=0.5, persistent=True)


def unregister_connection_monitor():
    global _CONNECTION_TIMER_REGISTERED
    _CONNECTION_TIMER_REGISTERED = False
    try:
        if bpy.app.timers.is_registered(_connection_timer):
            bpy.app.timers.unregister(_connection_timer)
    except Exception:
        pass


def _encode_multipart(fields, file_field, file_path, boundary, upload_filename=None):
    body = bytearray()
    crlf = b"\r\n"
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(crlf)

    filename = upload_filename or os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode("ascii"))
    body.extend(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
    with open(file_path, "rb") as handle:
        body.extend(handle.read())
    body.extend(crlf)
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body)


def upload_image(server_url, file_path, subfolder, remote_name=None, timeout=30.0):
    boundary = f"----ViewTexForge{uuid.uuid4().hex}"
    fields = {
        "overwrite": "true",
        "subfolder": subfolder,
        "type": "input",
    }
    body = _encode_multipart(fields, "image", file_path, boundary, upload_filename=remote_name)
    request = urllib.request.Request(
        f"{server_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))

    name = result.get("name") or remote_name or os.path.basename(file_path)
    returned_subfolder = result.get("subfolder", subfolder) or ""
    return f"{returned_subfolder.rstrip('/')}/{name}" if returned_subfolder else name


def _download_view(server_url, image_info, destination, timeout=30.0):
    params = urllib.parse.urlencode({
        "filename": image_info.get("filename", ""),
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    })
    request = urllib.request.Request(f"{server_url}/view?{params}", method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(data)


def _safe_name(value):
    text = str(value or "view")
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in text)
    return cleaned.strip("_") or "view"


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




def view_id_number(view_id):
    """Return the one-based numeric order encoded by a canonical view_#### id."""
    text = str(view_id or "").strip()
    prefix, sep, suffix = text.rpartition("_")
    if sep != "_" or prefix != "view" or len(suffix) != 4 or not suffix.isdigit():
        raise ValueError(f"Invalid view_id '{text}'. Expected format view_0001, view_0002, ...")
    number = int(suffix)
    if number < 1:
        raise ValueError(f"Invalid view_id '{text}'. Numbering starts at view_0001.")
    return number

def discover_latest_capture(output_dir):
    groups = {}
    if not os.path.isdir(output_dir):
        raise RuntimeError(f"Capture output directory does not exist: {output_dir}")

    for entry in os.scandir(output_dir):
        if not entry.is_dir():
            continue
        camera_json = os.path.join(entry.path, "camera.json")
        if not os.path.isfile(camera_json):
            continue
        try:
            with open(camera_json, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        capture_id = data.get("capture_id")
        view_id = data.get("view_id") or entry.name
        if not capture_id:
            continue
        try:
            view_number = view_id_number(view_id)
        except ValueError as exc:
            print(f"[ViewTexForge][Capture] Ignoring legacy/invalid view folder {entry.path}: {exc}")
            continue
        record = {
            "capture_id": capture_id,
            "view_id": view_id,
            "view_number": view_number,
            "folder": entry.path,
            "camera_json": camera_json,
            "clay": os.path.join(entry.path, "clay.png"),
            "depth": os.path.join(entry.path, "depth.png"),
            "mask": os.path.join(entry.path, "mask.png"),
            "mtime": os.path.getmtime(camera_json),
        }
        groups.setdefault(capture_id, []).append(record)

    if not groups:
        raise RuntimeError("No ViewTexForge capture folders containing camera.json were found.")

    capture_id, views = max(
        groups.items(),
        key=lambda item: max(v["mtime"] for v in item[1]),
    )
    views.sort(key=lambda v: v["view_number"])

    numbers = [v["view_number"] for v in views]
    expected = list(range(1, len(views) + 1))
    if numbers != expected:
        raise RuntimeError(
            f"Capture '{capture_id}' has non-contiguous view_ids: {numbers}. "
            f"Expected {expected} (view_0001 ... view_{len(views):04d})."
        )

    for view in views:
        for key in ("clay", "depth", "mask"):
            if not os.path.isfile(view[key]):
                raise RuntimeError(f"Missing {key}.png for view '{view['view_id']}': {view[key]}")

    return capture_id, views


def resolve_seed(base_seed, seed_mode, batch_index=0):
    base_seed = max(0, int(base_seed))
    if seed_mode == "INCREMENT":
        return base_seed + int(batch_index)
    if seed_mode == "RANDOM":
        return secrets.randbelow(2_147_483_648)
    return base_seed


class ComfyUIGenerationWorker(threading.Thread):
    def __init__(self, *, server_url, workflow_path, reference_path, output_dir, seed_mode, base_seed, event_queue):
        super().__init__(daemon=True, name="ViewTexForge-ComfyUIGeneration")
        self.server_url = _normalize_base_url(server_url)
        self.workflow_path = workflow_path
        self.reference_path = reference_path
        self.output_dir = output_dir
        self.seed_mode = seed_mode
        self.base_seed = base_seed
        self.events = event_queue
        self.client_id = uuid.uuid4().hex
        self.job_id = uuid.uuid4().hex[:12]

    def emit(self, kind, **payload):
        self.events.put({"kind": kind, **payload})

    def progress(self, value, status):
        self.emit("progress", progress=max(0.0, min(100.0, float(value))), status=status)

    def run(self):
        try:
            self._run_impl()
        except Exception as exc:
            self.emit("error", message=str(exc))

    def _run_impl(self):
        self.progress(2, "Checking ComfyUI connection...")
        ok, error = check_connection(self.server_url, timeout=2.0)
        if not ok:
            raise RuntimeError(f"ComfyUI connection failed: {error}")

        if not os.path.isfile(self.workflow_path):
            raise RuntimeError(f"Workflow JSON not found: {self.workflow_path}")
        if not os.path.isfile(self.reference_path):
            raise RuntimeError(f"Reference image not found: {self.reference_path}")

        self.progress(5, "Finding latest ViewTexForge capture...")
        capture_id, views = discover_latest_capture(self.output_dir)
        self.emit("capture", capture_id=capture_id, total_views=len(views))
        self.emit("mapping", views=[v["view_id"] for v in views])

        with open(self.workflow_path, "r", encoding="utf-8") as handle:
            workflow = json.load(handle)
        valid, errors, contract = validate_workflow(workflow)
        if not valid:
            raise RuntimeError("Workflow validation failed. See Blender system console for details.")
        if len(views) != contract["view_count"]:
            raise RuntimeError(
                f"Workflow expects {contract['view_count']} views, but capture '{capture_id}' contains {len(views)}."
            )

        resolved_seed = resolve_seed(self.base_seed, self.seed_mode, 0)
        self.emit("seed", seed=resolved_seed)

        subfolder = f"viewtexforge/{self.job_id}"
        upload_items = []
        for view in views:
            upload_items.extend([
                (view["view_id"], "clay", view["clay"]),
                (view["view_id"], "depth", view["depth"]),
                (view["view_id"], "mask", view["mask"]),
            ])
        upload_items.append(("reference", "reference", self.reference_path))

        uploaded = {}
        total_uploads = len(upload_items)
        view_ordinals = {str(view["view_id"]): int(view["view_number"]) for view in views}
        for index, (view_id, kind, path) in enumerate(upload_items):
            pct = 8 + (24.0 * index / max(total_uploads, 1))
            self.progress(pct, f"Uploading {kind}: {view_id}")
            extension = os.path.splitext(path)[1].lower() or ".png"
            if view_id == "reference":
                remote_name = f"reference{extension}"
            else:
                ordinal = view_ordinals[str(view_id)]
                remote_name = f"{ordinal:02d}_{_safe_name(view_id)}_{kind}{extension}"
            uploaded[(view_id, kind)] = upload_image(
                self.server_url, path, subfolder, remote_name=remote_name
            )

        print("[ViewTexForge][ComfyUI Input Mapping]")
        for index, view in enumerate(views):
            view_id = view["view_id"]
            display_role = " (Front)" if view.get("view_number") == 1 else ""
            print(f"  Input {index + 1:02d} -> {view_id}{display_role}")
            print(f"    Source: {uploaded[(view_id, 'clay')]}")
            print(f"    Depth : {uploaded[(view_id, 'depth')]}")
            print(f"    Mask  : {uploaded[(view_id, 'mask')]}")
        print(f"  Reference: {uploaded[('reference', 'reference')]}")

        # Keep one consistent view order across source/depth/mask and output tile mapping.
        for index, node_id in enumerate(contract["source_nodes"]):
            workflow[node_id]["inputs"]["image"] = uploaded[(views[index]["view_id"], "clay")]
        for index, node_id in enumerate(contract["depth_nodes"]):
            workflow[node_id]["inputs"]["image"] = uploaded[(views[index]["view_id"], "depth")]
        for index, node_id in enumerate(contract["mask_nodes"]):
            workflow[node_id]["inputs"]["image"] = uploaded[(views[index]["view_id"], "mask")]
        workflow[contract["reference_node"]]["inputs"]["image"] = uploaded[("reference", "reference")]
        workflow[contract["seed_node"]]["inputs"]["seed"] = resolved_seed

        # ComfyUI-side output location/prefix are controlled by the workflow contract.
        workflow[contract["output_dir_node"]].setdefault("inputs", {})["value"] = "ViewTexForge_output"
        workflow[contract["output_prefix_node"]].setdefault("inputs", {})["value"] = f"generated_{self.job_id}"

        self.progress(34, "Submitting workflow to ComfyUI...")
        response = _http_json(
            f"{self.server_url}/prompt",
            method="POST",
            payload={"prompt": workflow, "client_id": self.client_id},
            timeout=10.0,
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {response}")
        self.emit("prompt", prompt_id=prompt_id)

        self.progress(40, "Queued in ComfyUI...")
        history_entry = None
        start = time.monotonic()
        last_status = None
        poll_count = 0
        # HTTP polling cannot read the stdout of an independently launched
        # ComfyUI console and /queue does not expose per-node/sampler progress.
        # Keep the progress visibly alive while ComfyUI is running by advancing
        # an estimated workflow percentage toward (but never beyond) 88%.
        # Completion is still determined authoritatively from /history.
        estimated_running_progress = 52.0
        while history_entry is None:
            poll_count += 1
            history = _http_json(f"{self.server_url}/history/{urllib.parse.quote(prompt_id)}", timeout=5.0)
            if isinstance(history, dict) and prompt_id in history:
                history_entry = history[prompt_id]
                break

            # /queue does not expose sampler percentage, but distinguishes queued/running.
            try:
                queue_state = _http_json(f"{self.server_url}/queue", timeout=3.0)
                running_ids = {
                    str(item[1]) for item in (queue_state.get("queue_running") or [])
                    if isinstance(item, (list, tuple)) and len(item) > 1
                }
                pending_ids = {
                    str(item[1]) for item in (queue_state.get("queue_pending") or [])
                    if isinstance(item, (list, tuple)) and len(item) > 1
                }
                elapsed = max(0.0, time.monotonic() - start)
                elapsed_text = time.strftime("%M:%S", time.gmtime(elapsed))
                if prompt_id in running_ids:
                    # Monotonic estimated progress: each successful poll moves
                    # the bar a little, with a soft cap. It communicates activity
                    # without pretending HTTP polling knows the exact sampler %.
                    estimated_running_progress = min(88.0, estimated_running_progress + 0.22)
                    pct = estimated_running_progress
                    status = f"ComfyUI running | {elapsed_text} | poll {poll_count}"
                elif prompt_id in pending_ids:
                    pct = max(45.0, min(51.0, 45.0 + poll_count * 0.05))
                    status = f"Waiting in ComfyUI queue | {elapsed_text} | poll {poll_count}"
                else:
                    estimated_running_progress = min(88.0, max(estimated_running_progress, 52.0) + 0.08)
                    pct = estimated_running_progress
                    status = f"Waiting for ComfyUI result | {elapsed_text} | poll {poll_count}"

                # Emit every poll so the UI always shows visible activity.
                self.progress(pct, status)
                last_status = status
            except Exception:
                pass

            if time.monotonic() - start > 60 * 60:
                raise RuntimeError("Timed out waiting for ComfyUI after 60 minutes.")
            time.sleep(0.75)

        status_info = history_entry.get("status") or {}
        if status_info.get("status_str") == "error" or status_info.get("completed") is False:
            messages = status_info.get("messages") or []
            raise RuntimeError(f"ComfyUI workflow failed: {messages or status_info}")

        outputs = history_entry.get("outputs") or {}
        save_output = outputs.get(contract["save_node"]) or {}
        image_infos = save_output.get("images") or []
        if len(image_infos) < len(views):
            raise RuntimeError(
                f"Expected at least {len(views)} output images from SaveImage node "
                f"{contract['save_node']}, got {len(image_infos)}."
            )

        generated_dir = os.path.join(self.output_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)
        manifest_outputs = []
        for index, view in enumerate(views):
            pct = 75 + 18.0 * index / max(len(views), 1)
            self.progress(pct, f"Downloading result: {view['view_id']}")
            filename = f"{_safe_name(view['view_id'])}.png"
            destination = os.path.join(generated_dir, filename)
            _download_view(self.server_url, image_infos[index], destination)
            manifest_outputs.append({
                "view_id": view["view_id"],
                "camera_json": os.path.relpath(view["camera_json"], self.output_dir).replace("\\", "/"),
                "source_clay": os.path.relpath(view["clay"], self.output_dir).replace("\\", "/"),
                "source_depth": os.path.relpath(view["depth"], self.output_dir).replace("\\", "/"),
                "source_mask": os.path.relpath(view["mask"], self.output_dir).replace("\\", "/"),
                "generated_image": os.path.relpath(destination, self.output_dir).replace("\\", "/"),
                "comfyui_output": image_infos[index],
            })

        self.progress(95, "Writing generated manifest...")
        manifest = {
            "schema_version": 1,
            "producer": {"name": "ViewTexForge", "feature": "ComfyUI Generation"},
            "capture_id": capture_id,
            "job_id": self.job_id,
            "server_url": self.server_url,
            "workflow": {
                "path": os.path.abspath(self.workflow_path),
                "sha256": _sha256_file(self.workflow_path),
                "contract": "ViewTexForge Workflow Contract v1",
            },
            "reference_image": {
                "path": os.path.abspath(self.reference_path),
                "sha256": _sha256_file(self.reference_path),
            },
            "seed": {
                "mode": self.seed_mode,
                "base": int(self.base_seed),
                "resolved": int(resolved_seed),
            },
            "outputs": manifest_outputs,
        }
        manifest_path = os.path.join(generated_dir, "generated_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=4, ensure_ascii=False)

        self.progress(100, "Generation completed")
        self.emit(
            "done",
            manifest_path=manifest_path,
            generated_dir=generated_dir,
            prompt_id=prompt_id,
            seed=resolved_seed,
        )
