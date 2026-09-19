"""视频/音频格式和编码配置。"""
from dataclasses import dataclass, field
from enum import Enum


class ContainerFormat(str, Enum):
    MP4 = "mp4"
    MKV = "mkv"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"
    FLV = "flv"
    TS = "ts"
    M4A = "m4a"
    FLAC = "flac"
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    JPG = "jpg"
    PNG = "png"
    GIF = "gif"
    WEBP = "webp"
    BMP = "bmp"
    RAW = "raw"  # 不处理

    @property
    def label(self) -> str:
        return _CONTAINER_LABELS.get(self.value, self.value)

    @property
    def is_video(self) -> bool:
        return self in (self.MP4, self.MKV, self.AVI, self.MOV, self.WEBM, self.FLV, self.TS)

    @property
    def is_audio(self) -> bool:
        return self in (self.M4A, self.FLAC, self.MP3, self.WAV, self.OGG)

    @property
    def is_image(self) -> bool:
        return self in (self.JPG, self.PNG, self.GIF, self.WEBP, self.BMP)


_CONTAINER_LABELS = {
    "mp4": "MP4 (H.264/AAC)", "mkv": "MKV (Matroska)", "avi": "AVI",
    "mov": "MOV (QuickTime)", "webm": "WebM (VP9/Opus)", "flv": "FLV",
    "ts": "MPEG-TS", "m4a": "M4A (AAC 音频)", "flac": "FLAC (无损音频)",
    "mp3": "MP3", "wav": "WAV (无压缩)", "ogg": "OGG (Vorbis)",
    "jpg": "JPEG 图片", "png": "PNG 图片", "gif": "GIF 动图",
    "webp": "WebP 图片", "bmp": "BMP 图片", "raw": "原始 (不处理)",
}


@dataclass
class VideoCodec:
    name: str
    ffmpeg_name: str  # FFmpeg 编码器名称
    ext_hint: str     # 推荐扩展名


VIDEO_CODECS = {
    "h264": VideoCodec("H.264 / AVC", "libx264", "mp4"),
    "h265": VideoCodec("H.265 / HEVC", "libx265", "mp4"),
    "h265_vt": VideoCodec("H.265 (VT 硬件)", "hevc_videotoolbox", "mp4"),
    "h265_nv": VideoCodec("H.265 (NVENC)", "hevc_nvenc", "mp4"),
    "h265_qsv": VideoCodec("H.265 (QSV)", "hevc_qsv", "mp4"),
    "av1": VideoCodec("AV1", "libsvtav1", "webm"),
    "av1_nv": VideoCodec("AV1 (NVENC)", "av1_nvenc", "mp4"),
    "vp8": VideoCodec("VP8", "libvpx", "webm"),
    "vp9": VideoCodec("VP9", "libvpx-vp9", "webm"),
    "mpeg4": VideoCodec("MPEG-4", "mpeg4", "avi"),
    "copy": VideoCodec("直接复制 (不转码)", "copy", "mp4"),
}


@dataclass
class AudioCodec:
    name: str
    ffmpeg_name: str
    ext_hint: str


AUDIO_CODECS = {
    "aac": AudioCodec("AAC", "aac", "m4a"),
    "aac_128": AudioCodec("AAC 128kbps", "aac -b:a 128k", "m4a"),
    "aac_192": AudioCodec("AAC 192kbps", "aac -b:a 192k", "m4a"),
    "aac_256": AudioCodec("AAC 256kbps", "aac -b:a 256k", "m4a"),
    "aac_320": AudioCodec("AAC 320kbps", "aac -b:a 320k", "m4a"),
    "mp3": AudioCodec("MP3", "libmp3lame", "mp3"),
    "mp3_128": AudioCodec("MP3 128kbps", "libmp3lame -b:a 128k", "mp3"),
    "mp3_320": AudioCodec("MP3 320kbps", "libmp3lame -b:a 320k", "mp3"),
    "flac": AudioCodec("FLAC (无损)", "flac", "flac"),
    "opus": AudioCodec("Opus", "libopus", "ogg"),
    "vorbis": AudioCodec("Vorbis", "libvorbis", "ogg"),
    "pcm_s16le": AudioCodec("PCM 16-bit", "pcm_s16le", "wav"),
    "pcm_s24le": AudioCodec("PCM 24-bit", "pcm_s24le", "wav"),
    "copy": AudioCodec("直接复制", "copy", "m4a"),
}


@dataclass
class OutputProfile:
    """预设输出配置。"""
    name: str
    container: ContainerFormat
    video_codec: str = "copy"
    audio_codec: str = "copy"


OUTPUT_PROFILES = {
    "mp4_copy": OutputProfile("MP4 直接复制", ContainerFormat.MP4),
    "mp4_h264": OutputProfile("MP4 H.264", ContainerFormat.MP4, "h264", "aac"),
    "mp4_h265": OutputProfile("MP4 H.265", ContainerFormat.MP4, "h265", "aac"),
    "mkv_copy": OutputProfile("MKV 直接复制", ContainerFormat.MKV),
    "mkv_h264": OutputProfile("MKV H.264", ContainerFormat.MKV, "h264", "aac"),
    "mkv_h265": OutputProfile("MKV H.265", ContainerFormat.MKV, "h265", "aac"),
    "webm_vp9": OutputProfile("WebM VP9", ContainerFormat.WEBM, "vp9", "opus"),
    "m4a_aac": OutputProfile("M4A AAC (仅音频)", ContainerFormat.M4A, "copy", "aac"),
    "mp3_copy": OutputProfile("MP3 (仅音频)", ContainerFormat.MP3, "copy", "mp3"),
    "flac_copy": OutputProfile("FLAC 无损 (仅音频)", ContainerFormat.FLAC, "copy", "flac"),
    "raw": OutputProfile("原始 (不处理)", ContainerFormat.RAW),
}


def build_ffmpeg_args(
    input_path: str,
    output_path: str,
    profile: OutputProfile,
) -> list[str]:
    """根据输出配置构建 FFmpeg 命令参数。"""
    args = ["-y", "-i", input_path]
    if profile.container == ContainerFormat.RAW:
        return ["-y", "-i", input_path, "-c", "copy", output_path]
    if profile.container.is_video:
        if profile.video_codec == "copy":
            args.extend(["-c:v", "copy"])
        else:
            vc = VIDEO_CODECS.get(profile.video_codec)
            args.extend(["-c:v", vc.ffmpeg_name if vc else profile.video_codec])
        if profile.audio_codec == "copy":
            args.extend(["-c:a", "copy"])
        else:
            ac = AUDIO_CODECS.get(profile.audio_codec)
            args.extend(["-c:a", ac.ffmpeg_name if ac else profile.audio_codec])
    elif profile.container.is_audio:
        if profile.audio_codec == "copy":
            args.extend(["-vn", "-c:a", "copy"])
        else:
            ac = AUDIO_CODECS.get(profile.audio_codec)
            args.extend(["-vn", "-c:a", ac.ffmpeg_name if ac else profile.audio_codec])
    args.append(output_path)
    return args


def get_extension_for_profile(profile: OutputProfile) -> str:
    return profile.container.value
