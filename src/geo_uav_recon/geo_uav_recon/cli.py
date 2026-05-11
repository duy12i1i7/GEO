from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import export_colmap_openmvs, merge_depths, run_benchmark, write_real_benchmark_config
from .dataset import summarize_dataset, validate_dataset_root
from .predictors import export_model_depths
from .realdata import describe_odm_sources, export_dronescapes_subset, prepare_odm_dataset
from .risk import select_frames


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geo_uav_recon.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    odm_sources = sub.add_parser("odm-sources")

    prepare_odm = sub.add_parser("prepare-odm")
    prepare_odm.add_argument("--output-dir", required=True)
    prepare_odm.add_argument("--sample-name", default="mygla")
    prepare_odm.add_argument("--archive-path")
    prepare_odm.add_argument("--source-url")
    prepare_odm.add_argument("--download-dir")

    dr_subset = sub.add_parser("dronescapes-subset")
    dr_subset.add_argument("--output-dir", required=True)
    dr_subset.add_argument("--repo-id", default="Meehai/dronescapes")
    dr_subset.add_argument("--split", default="test_set_annotated_only")
    dr_subset.add_argument("--rgb-modality", default="rgb")
    dr_subset.add_argument("--depth-modality", default="depth_sfm_manual202204")
    dr_subset.add_argument("--scene-prefix", action="append", default=[])
    dr_subset.add_argument("--max-frames", type=int, default=0)
    dr_subset.add_argument("--start-index", type=int, default=0)
    dr_subset.add_argument("--local-root")

    validate = sub.add_parser("validate-dataset")
    validate.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    validate.add_argument("--dataset-root", required=True)

    write_cfg = sub.add_parser("write-real-config")
    write_cfg.add_argument("--config-path", required=True)
    write_cfg.add_argument("--output-dir", required=True)
    write_cfg.add_argument("--python-bin", required=True)
    write_cfg.add_argument("--top-k-frames", type=int, default=16)
    write_cfg.add_argument("--risk-neighbors", type=int, default=6)
    write_cfg.add_argument("--coarse-image-size", type=int, default=224)
    write_cfg.add_argument("--refine-image-size", type=int, default=512)
    write_cfg.add_argument("--coarse-device", default="cpu")
    write_cfg.add_argument("--refine-device", default="cpu")
    write_cfg.add_argument("--window-size", type=int, default=2)
    write_cfg.add_argument("--batch-size", type=int, default=1)
    write_cfg.add_argument("--odm-root")
    write_cfg.add_argument("--dronescapes-root")
    write_cfg.add_argument("--colmap-bin")
    write_cfg.add_argument("--openmvs-bin-dir")
    write_cfg.add_argument("--skip-colmap-openmvs", action="store_true")

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--config", required=True)
    benchmark.add_argument("--output-dir", required=True)

    select = sub.add_parser("select-frames")
    select.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    select.add_argument("--dataset-root", required=True)
    select.add_argument("--output-dir", required=True)
    select.add_argument("--top-k-frames", type=int, required=True)
    select.add_argument("--strategy", default="risk")
    select.add_argument("--risk-neighbors", type=int, default=6)
    select.add_argument("--allow-depth-prior", action="store_true")

    dust3r = sub.add_parser("dust3r-export")
    dust3r.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    dust3r.add_argument("--dataset-root", required=True)
    dust3r.add_argument("--output-dir", required=True)
    dust3r.add_argument("--model-name", default="naver/DUSt3R_ViTLarge_BaseDecoder_224_linear")
    dust3r.add_argument("--image-size", type=int, default=224)
    dust3r.add_argument("--device", default="cpu")
    dust3r.add_argument("--window-size", type=int, default=2)
    dust3r.add_argument("--batch-size", type=int, default=1)
    dust3r.add_argument("--frame-list")

    mast3r = sub.add_parser("mast3r-export")
    mast3r.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    mast3r.add_argument("--dataset-root", required=True)
    mast3r.add_argument("--output-dir", required=True)
    mast3r.add_argument("--model-name", default="naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric")
    mast3r.add_argument("--image-size", type=int, default=512)
    mast3r.add_argument("--device", default="cpu")
    mast3r.add_argument("--window-size", type=int, default=2)
    mast3r.add_argument("--batch-size", type=int, default=1)
    mast3r.add_argument("--frame-list")

    merge = sub.add_parser("merge-depths")
    merge.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    merge.add_argument("--dataset-root", required=True)
    merge.add_argument("--output-dir", required=True)
    merge.add_argument("--source-depth-dir", required=True)
    merge.add_argument("--refine-depth-dir", required=True)
    merge.add_argument("--frame-list", required=True)
    merge.add_argument("--runtime-sec", type=float, required=True)

    export_colmap = sub.add_parser("colmap-openmvs-export")
    export_colmap.add_argument("--dataset-kind", choices=["odmdata", "dronescapes"], required=True)
    export_colmap.add_argument("--dataset-root", required=True)
    export_colmap.add_argument("--colmap-workspace", required=True)
    export_colmap.add_argument("--openmvs-root", required=True)
    export_colmap.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "odm-sources":
        print(json.dumps(describe_odm_sources(), indent=2))
        return 0
    if args.command == "prepare-odm":
        print(json.dumps(prepare_odm_dataset(args.output_dir, args.sample_name, args.archive_path, args.source_url, args.download_dir), indent=2))
        return 0
    if args.command == "dronescapes-subset":
        print(json.dumps(export_dronescapes_subset(args.output_dir, args.repo_id, args.split, args.rgb_modality, args.depth_modality, args.scene_prefix, args.max_frames, args.start_index, args.local_root), indent=2))
        return 0
    if args.command == "validate-dataset":
        print(json.dumps(validate_dataset_root(args.dataset_kind, args.dataset_root), indent=2))
        return 0
    if args.command == "write-real-config":
        print(json.dumps(write_real_benchmark_config(
            config_path=args.config_path,
            output_dir=args.output_dir,
            python_bin=args.python_bin,
            top_k_frames=args.top_k_frames,
            risk_neighbors=args.risk_neighbors,
            coarse_image_size=args.coarse_image_size,
            refine_image_size=args.refine_image_size,
            coarse_device=args.coarse_device,
            refine_device=args.refine_device,
            window_size=args.window_size,
            batch_size=args.batch_size,
            odm_root=args.odm_root,
            dronescapes_root=args.dronescapes_root,
            colmap_bin=args.colmap_bin,
            openmvs_bin_dir=args.openmvs_bin_dir,
            skip_colmap_openmvs=args.skip_colmap_openmvs,
        ), indent=2))
        return 0
    if args.command == "benchmark":
        print(json.dumps(run_benchmark(args.config, args.output_dir), indent=2))
        return 0
    if args.command == "select-frames":
        print(json.dumps(select_frames(args.dataset_kind, args.dataset_root, args.output_dir, args.top_k_frames, args.strategy, args.risk_neighbors, args.allow_depth_prior), indent=2))
        return 0
    if args.command == "dust3r-export":
        print(json.dumps(export_model_depths("dust3r", args.dataset_kind, args.dataset_root, args.output_dir, args.model_name, args.image_size, args.device, args.window_size, args.batch_size, args.frame_list), indent=2))
        return 0
    if args.command == "mast3r-export":
        print(json.dumps(export_model_depths("mast3r", args.dataset_kind, args.dataset_root, args.output_dir, args.model_name, args.image_size, args.device, args.window_size, args.batch_size, args.frame_list), indent=2))
        return 0
    if args.command == "merge-depths":
        print(json.dumps(merge_depths(args.dataset_kind, args.dataset_root, args.output_dir, args.source_depth_dir, args.refine_depth_dir, args.frame_list, args.runtime_sec), indent=2))
        return 0
    if args.command == "colmap-openmvs-export":
        print(json.dumps(export_colmap_openmvs(args.colmap_workspace, args.openmvs_root, args.output_dir, args.dataset_kind, args.dataset_root), indent=2))
        return 0
    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
