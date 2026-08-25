from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to generate showcase assets")

    ASSETS.mkdir(parents=True, exist_ok=True)

    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x273043:s=960x540:d=1",
        "-vf",
        "drawbox=x=90:y=80:w=780:h=380:color=0x3a86ff@0.9:t=fill,drawbox=x=150:y=140:w=660:h=260:color=0x111827@0.92:t=fill",
        "-frames:v",
        "1",
        str(ASSETS / "card.png"),
    )

    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=960x540:rate=30:duration=6",
        "-vf",
        "drawbox=x=40+60*t:y=360:w=180:h=90:color=0x8338ec@0.75:t=fill",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(ASSETS / "motion.mp4"),
    )

    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=196:sample_rate=48000:duration=20",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=294:sample_rate=48000:duration=20",
        "-filter_complex",
        "[0:a]volume=0.08[a0];[1:a]volume=0.035[a1];[a0][a1]amix=inputs=2:normalize=0,afade=t=in:st=0:d=1,afade=t=out:st=18:d=2[a]",
        "-map",
        "[a]",
        "-c:a",
        "pcm_s16le",
        str(ASSETS / "bed.wav"),
    )

    print(f"Generated showcase assets in {ASSETS}")


if __name__ == "__main__":
    main()
