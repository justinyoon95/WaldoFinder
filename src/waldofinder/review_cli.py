"""Local human review and manual panel marking; never changes source labels."""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .annotations import AnnotationError, image_path, load_annotations
from .geometry import all_exclusions, valid_polygon
from .review import DECISIONS, find_scene, load_review, save_review, validate_review, valid_rectangle
from .tiling import plan_tiles


def display_rectangle(start, end, display_size, original_size):
    """Convert a drag in a fitted display into original-image pixel edges."""
    dw, dh = display_size
    width, height = original_size
    x1, x2 = sorted((max(0, min(dw, start[0])), max(0, min(dw, end[0]))))
    y1, y2 = sorted((max(0, min(dh, start[1])), max(0, min(dh, end[1]))))
    if x1 == x2 or y1 == y2:
        raise AnnotationError("Draw a rectangle with positive width and height")
    return [math.floor(x1 * width / dw), math.floor(y1 * height / dh),
            math.ceil(x2 * width / dw), math.ceil(y2 * height / dh)]


def render_review(record, scene, image_root):
    with Image.open(image_path(Path(image_root), record["file_name"])) as source:
        image = source.convert("RGB")
    shading = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay = ImageDraw.Draw(shading)
    for rectangle in scene["exclusion_rectangles"]:
        x1, y1, x2, y2 = rectangle["bbox"]
        overlay.rectangle((math.floor(x1), math.floor(y1), math.ceil(x2)-1, math.ceil(y2)-1),
                          fill=(0, 180, 255, 55), outline=(0, 120, 255, 255), width=3)
        overlay.text((x1, y1), rectangle["id"], fill="blue", stroke_width=1, stroke_fill="white")
    for polygon in scene.get("exclusion_polygons", []):
        points = [tuple(p) for p in polygon["points"]]
        overlay.polygon(points, fill=(0, 180, 255, 55))
        overlay.line(points + [points[0]], fill=(0, 120, 255, 255), width=3)
        overlay.text(points[0], polygon["id"], fill="blue", stroke_width=1, stroke_fill="white")
    image = Image.alpha_composite(image.convert("RGBA"), shading).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {"hidden_scene_waldo": "green", "portrait_or_guide": "darkorange", "unreviewed": "red"}
    for box in scene["boxes"]:
        x1, y1, x2, y2 = box["bbox"]
        color = colors[box["decision"]]
        draw.rectangle((math.floor(x1), math.floor(y1), math.ceil(x2)-1, math.ceil(y2)-1),
                       outline=color, width=max(2, min(image.size)//500))
        draw.text((x1, max(0, y1-12)), f"{box['preview_label']}: {box['decision']}",
                  fill=color, stroke_width=1, stroke_fill="white")
    return image


def draw_rectangle(image):
    """Open a native Tk window. Only Save returns a user-drawn rectangle."""
    try:
        import tkinter as tk
        from PIL import ImageTk
    except ImportError as exc:
        raise AnnotationError("Drawing requires Python with Tk; alternatively pass --box xmin ymin xmax ymax") from exc
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise AnnotationError("Cannot open a drawing window; use a desktop terminal or pass --box") from exc
    window.title("WaldoFinder: manually exclude a whole panel")
    scale = min(1, (window.winfo_screenwidth()-100)/image.width,
                (window.winfo_screenheight()-180)/image.height)
    display_size = (max(1, int(image.width*scale)), max(1, int(image.height*scale)))
    photo = ImageTk.PhotoImage(image.resize(display_size, Image.Resampling.LANCZOS))
    tk.Label(window, text="Drag around the WHOLE instruction panel or guide. Drag again to redraw. Save commits this rectangle only.").pack()
    canvas = tk.Canvas(window, width=display_size[0], height=display_size[1], highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, image=photo, anchor="nw")
    status = tk.StringVar(value="No rectangle selected")
    tk.Label(window, textvariable=status).pack()
    state = {"start": None, "shape": None, "candidate": None, "saved": None}

    def press(event):
        if state["shape"] is not None:
            canvas.delete(state["shape"])
        state["start"] = (event.x, event.y)
        state["candidate"] = None
        state["shape"] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="blue", width=3)

    def motion(event):
        if state["start"] is not None:
            canvas.coords(state["shape"], *state["start"], event.x, event.y)

    def release(event):
        if state["start"] is None:
            return
        try:
            state["candidate"] = display_rectangle(state["start"], (event.x, event.y), display_size, image.size)
            status.set(f"Original-pixel XYXY: {state['candidate']}")
        except AnnotationError as exc:
            status.set(str(exc))
        state["start"] = None

    def save():
        if state["candidate"] is None:
            status.set("Draw a nonempty rectangle first")
            return
        state["saved"] = state["candidate"]
        window.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", motion)
    canvas.bind("<ButtonRelease-1>", release)
    buttons = tk.Frame(window)
    buttons.pack()
    tk.Button(buttons, text="Save rectangle", command=save).pack(side="left")
    tk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left")
    window.mainloop()
    return state["saved"]


def display_point(point, display_size, original_size):
    """Map one clicked corner to original pixels without imposing a rectangle."""
    return [max(0, min(display_size[i], point[i])) * original_size[i] / display_size[i] for i in (0, 1)]


def draw_polygon(image):
    """Collect four human-clicked corners; only Save polygon commits them."""
    try:
        import tkinter as tk
        from PIL import ImageTk
    except ImportError as exc:
        raise AnnotationError("Drawing requires Python with Tk; alternatively supply --points") from exc
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise AnnotationError("Cannot open drawing window; use a desktop terminal or --points") from exc
    window.title("WaldoFinder: four-corner panel exclusion")
    scale = min(1, (window.winfo_screenwidth()-100)/image.width,
                (window.winfo_screenheight()-200)/image.height)
    size = (max(1, int(image.width*scale)), max(1, int(image.height*scale)))
    photo = ImageTk.PhotoImage(image.resize(size, Image.Resampling.LANCZOS))
    tk.Label(window, text="Click four panel corners around its perimeter: top-left, top-right, bottom-right, bottom-left. Then Save polygon.").pack()
    canvas = tk.Canvas(window, width=size[0], height=size[1], highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, image=photo, anchor="nw")
    status = tk.StringVar(value="Click corner 1 of 4")
    tk.Label(window, textvariable=status).pack()
    state = {"points": [], "saved": None}
    buttons = tk.Frame(window)
    buttons.pack()

    def redraw():
        canvas.delete("selection")
        points = state["points"]
        if len(points) > 1:
            chain = points + [points[0]] if len(points) == 4 else points
            canvas.create_line(*[n for p in chain for n in p], fill="blue", width=3, tags="selection")
        for i, (x, y) in enumerate(points, 1):
            canvas.create_oval(x-4, y-4, x+4, y+4, fill="blue", tags="selection")
            canvas.create_text(x+9, y+9, text=str(i), fill="blue", tags="selection")
        original = [display_point(p, size, image.size) for p in points]
        ready = valid_polygon(original, image.width, image.height)
        save_button.configure(state="normal" if ready else "disabled")
        if ready:
            status.set("Four valid corners selected. Check the outline, then click Save polygon.")
        elif len(points) == 4:
            status.set("Invalid shape: use Undo corner or Reset, then click corners around the perimeter.")
        else:
            status.set(f"Click corner {len(points)+1} of 4")

    def click(event):
        if len(state["points"]) < 4:
            state["points"].append([max(0, min(size[0], event.x)), max(0, min(size[1], event.y))])
            redraw()

    def undo():
        if state["points"]:
            state["points"].pop()
        redraw()

    def reset():
        state["points"].clear()
        redraw()

    def save():
        points = [display_point(p, size, image.size) for p in state["points"]]
        if valid_polygon(points, image.width, image.height):
            state["saved"] = points
            window.destroy()

    save_button = tk.Button(buttons, text="Save polygon", command=save, state="disabled")
    save_button.pack(side="left")
    tk.Button(buttons, text="Undo corner", command=undo).pack(side="left")
    tk.Button(buttons, text="Reset", command=reset).pack(side="left")
    tk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left")
    canvas.bind("<ButtonPress-1>", click)
    window.bind("<BackSpace>", lambda event: undo())
    window.mainloop()
    return state["saved"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations/charlie-db.json"))
    parser.add_argument("--reviews", type=Path, default=Path("data/annotations/charlie-db-review.json"))
    parser.add_argument("--images", type=Path, default=Path("data/images"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for name in ("show", "classify", "exclude", "remove-exclusion", "finish-regions", "plan"):
        command = commands.add_parser(name)
        command.add_argument("--scene", required=True)
        if name == "show":
            command.add_argument("--show", action="store_true")
        elif name == "classify":
            command.add_argument("--waldo", type=int, required=True, help="Number displayed as Waldo N in the original preview")
            command.add_argument("--decision", choices=sorted(DECISIONS), required=True)
        elif name == "exclude":
            command.add_argument("--id", required=True, help="A unique human-readable rectangle identifier")
            command.add_argument("--shape", choices=["rectangle", "polygon"], default="rectangle")
            command.add_argument("--replace", action="store_true", help="Replace an existing region with this ID only after Save; Cancel preserves it")
            command.add_argument("--reason", choices=["instruction_panel", "character_guide", "portrait_panel"], default="instruction_panel")
            command.add_argument("--box", type=float, nargs=4, metavar=("XMIN", "YMIN", "XMAX", "YMAX"), help="Original pixels; omit to draw in a native desktop window")
            command.add_argument("--points", type=float, nargs=8, help="Four original-pixel XY pairs in perimeter order; polygon mode only")
        elif name == "remove-exclusion":
            command.add_argument("--id", required=True)
        elif name == "plan":
            command.add_argument("--tile-size", type=int, default=512)
            command.add_argument("--stride", type=int, default=256)
    args = parser.parse_args(argv)
    try:
        records = load_annotations(args.annotations, args.images)
        review = load_review(args.reviews, records, args.annotations, args.images)
        if args.command == "status":
            for scene in review["images"]:
                states = ", ".join(f"{b['preview_label']}={b['decision']}" for b in scene["boxes"])
                print(f"{scene['scene_id']}: {states}; rectangles={len(scene['exclusion_rectangles'])}; polygons={len(scene.get('exclusion_polygons', []))}; regions reviewed={scene['exclusions_reviewed']}")
            return
        scene = find_scene(review, args.scene)
        record = next(r for r in records if r["file_name"] == scene["file_name"])
        # Use the validated manifest position for output names, never a path from --scene.
        output_stem = f"{records.index(record):02d}-{Path(record['file_name']).stem}"
        if args.command in {"show", "plan"}:
            folder = Path("outputs/review")
            folder.mkdir(parents=True, exist_ok=True)
            if args.command == "show":
                output = folder / f"{output_stem}.png"
                image = render_review(record, scene, args.images)
                image.save(output)
                print(f"Saved review preview: {output.resolve()}")
                if args.show:
                    image.show()
            else:
                plan = plan_tiles(record, scene, args.tile_size, args.stride)
                output = folder / f"{output_stem}-tile-plan.json"
                save_review(output, plan)
                print(f"Planned {len(plan['kept'])} kept and {len(plan['skipped'])} excluded tiles: {output.resolve()}")
            return
        if args.command == "classify":
            box = next((b for b in scene["boxes"] if b["preview_label"] == f"Waldo {args.waldo}"), None)
            if box is None:
                raise AnnotationError("No matching preview label in this scene")
            box.update(decision=args.decision, reviewed_by="user")
        elif args.command == "exclude":
            existing = next((r for r in all_exclusions(scene) if r["id"] == args.id), None)
            if existing is not None and not args.replace:
                raise AnnotationError("Exclusion ID already exists; pass --replace to replace it after Save")
            if existing is None and args.replace:
                raise AnnotationError("No existing exclusion with that ID to replace")
            if args.shape == "polygon" and args.box is not None or args.shape == "rectangle" and args.points is not None:
                raise AnnotationError("Use --points with polygon mode or --box with rectangle mode")
            # Hide the old region for drawing only. It remains saved until Save.
            drawing_scene = dict(scene)
            for key in ("exclusion_rectangles", "exclusion_polygons"):
                drawing_scene[key] = [r for r in scene.get(key, []) if r["id"] != args.id]
            if args.shape == "polygon":
                geometry = [args.points[i:i+2] for i in range(0, 8, 2)] if args.points is not None else None
            else:
                geometry = args.box
            if geometry is None:
                drawing = render_review(record, drawing_scene, args.images)
                geometry = draw_polygon(drawing) if args.shape == "polygon" else draw_rectangle(drawing)
                if geometry is None:
                    print("Canceled; review unchanged")
                    return
            validator = valid_polygon if args.shape == "polygon" else valid_rectangle
            if not validator(geometry, record["width"], record["height"]):
                raise AnnotationError("Invalid exclusion geometry; polygons need four convex corners in perimeter order inside the original image")
            # A drawing window may stay open while other decisions are saved.
            # Reload to preserve them, and reject a concurrent change to this ID.
            review = load_review(args.reviews, records, args.annotations, args.images)
            scene = find_scene(review, args.scene)
            latest = next((r for r in all_exclusions(scene) if r["id"] == args.id), None)
            if latest != existing:
                raise AnnotationError("This exclusion changed while drawing; reopen it before replacing")
            if args.replace:
                for key in ("exclusion_rectangles", "exclusion_polygons"):
                    scene[key] = [r for r in scene.get(key, []) if r["id"] != args.id]
            key, field = ("exclusion_polygons", "points") if args.shape == "polygon" else ("exclusion_rectangles", "bbox")
            scene.setdefault(key, []).append({"id": args.id, field: geometry,
                "reason": args.reason, "reviewed_by": "user"})
            scene["exclusions_reviewed"] = False
        elif args.command == "remove-exclusion":
            if not any(r["id"] == args.id for r in all_exclusions(scene)):
                raise AnnotationError("No exclusion with that ID")
            for key in ("exclusion_rectangles", "exclusion_polygons"):
                scene[key] = [r for r in scene.get(key, []) if r["id"] != args.id]
            scene["exclusions_reviewed"] = False
        elif args.command == "finish-regions":
            scene["exclusions_reviewed"] = True
        validate_review(review, records, args.annotations, args.images)
        save_review(args.reviews, review)
        print(f"Saved human review: {args.reviews.resolve()}")
    except (AnnotationError, OSError, ValueError) as exc:
        parser.exit(1, f"Review failed: {exc}\n")


if __name__ == "__main__":
    main()
