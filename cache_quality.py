"""Read and bind NetEase cache quality metadata to its audio resource."""
import json
from pathlib import Path

LEVEL_NAMES = {"standard": "标准", "higher": "较高", "exhigh": "极高 HQ",
               "lossless": "无损 SQ", "hires": "高清臻音", "jymaster": "超清母带",
               "vivid": "臻音全景声（Audio Vivid）"}

def decode_info(raw: bytes) -> dict:
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        decoded = bytes((((((v ^ 59) & 15) ^ ((v ^ 59) >> 4)) << 4) | ((v ^ 59) >> 4)) for v in raw)
        result = json.loads(decoded)
    if not isinstance(result, dict):
        raise ValueError("缓存信息不是对象")
    return result

def resolve_cache_quality(cache_file: Path) -> dict:
    unknown = {"quality_label": "档位未知", "quality_status": "unknown"}
    try:
        info = decode_info(cache_file.with_suffix(".info").read_bytes())
        resource_md5 = str(info.get("md5", "")).lower()
        filename_md5 = cache_file.stem.rsplit("-", 1)[-1].lower()
        if len(resource_md5) != 32 or resource_md5 != filename_md5:
            raise ValueError("品质信息的资源 MD5 与缓存文件名不匹配")
        if int(info.get("size", -1)) != cache_file.stat().st_size:
            raise ValueError("品质信息的资源大小与缓存文件不匹配，可能是未完成缓存")
        level = str(info.get("level", ""))
        if level not in LEVEL_NAMES:
            raise ValueError(f"未识别的网易云档位：{level or '缺失'}")
        return {"quality_label": LEVEL_NAMES[level], "quality_status": "confirmed",
                "quality_basis": f"缓存 .info 明确记录 level={level}；资源 MD5 与文件名、资源大小均匹配",
                "netease_level": level, "quality_resource_md5": resource_md5}
    except (OSError, ValueError, TypeError) as exc:
        return {**unknown, "quality_basis": str(exc)}
