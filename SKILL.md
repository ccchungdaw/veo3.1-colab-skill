---
name: veo3.1-colab
description: Generate cinematic videos with native synchronized audio using Google Veo 3.1 via Google Colab CLI. Supports text-to-video, image-guided video, and sequential batch generation.
---

# Google Veo 3.1 on Colab

Use the bundled notebook and `scripts/runner.py` to generate high-fidelity videos with native audio using Google's **Veo 3.1** model via Google Colab CLI. The Colab CLI must be installed and authenticated, and a valid `GEMINI_API_KEY` (or Google Cloud authentication) is required.

## Key Capabilities of Veo 3.1

- **Native Synchronized Audio**: Generates synchronized atmospheric audio, dialogue, and sound effects natively alongside the visuals.
- **Aspect Ratios**: Supports landscape (`16:9`) and vertical portrait (`9:16`).
- **Resolutions**: Supports `720p`, `1080p`, and `4k`.
- **Duration**: Standard generation duration is 5 to 8 seconds.
- **Image Guidance**:
  - **First Frame (I2V)**: Initiates video motion starting from a specific image.
  - **Reference Images**: Uses 1 to 3 reference images (character appearance, background setting, or props) for consistent visual identity.
  - **First Frame + Last Frame**: Interpolates smoothly between a starting and ending frame.
- **Model Variants**:
  - `veo-3.1-generate-preview`: Highest fidelity, cinematic lighting, and fine detail.
  - `veo-3.1-fast-generate-preview`: Faster iteration, lower latency, and cost-efficient.

## Workflow

1. **Inspect User Request & Inputs**:
   - Check if the user supplied prompt text or a prompt file.
   - Check if reference images (0–3 images), a first frame, or a last frame are provided.
   - Determine desired aspect ratio (`16:9` or `9:16`), duration (5–8s), and model variant.
2. **Compose Prompt for Veo 3.1**:
   - Write a rich cinematic prompt describing:
     - **Subject & Action**: What is happening in the scene.
     - **Camera Motion**: e.g., "slow drone push-in", "low-angle panning shot", "orbital track".
     - **Lighting & Atmosphere**: e.g., "warm golden hour backlight", "neon cybernetic glow with volumetric fog".
     - **Audio & Sound**: Explicitly mention audio elements (e.g., "gentle rain tapping on glass with soft melancholy piano in the background").
3. **Check Prerequisites**:
   - Check Colab access and compute units with `python scripts/runner.py usage --json`.
     *(Note: Veo 3.1 runs API inference, so a standard CPU runtime or low-tier Colab runtime is sufficient; high-end A100 GPUs are NOT required, saving compute units!)*
   - Ensure `GEMINI_API_KEY` is present in the environment or Colab secrets.
4. **Execute Single Inference or Batch Manifest**:

### Single Video Execution

```bash
python scripts/runner.py single \
  --prompt /absolute/path/prompt.txt \
  --image /absolute/path/character.png \
  --aspect-ratio 16:9 \
  --duration 5 \
  --output /absolute/path/output.mp4
```

Or using the helper launcher script:
```bash
./run_colab_inference.sh \
  --image /absolute/path/character.png \
  --prompt /absolute/path/prompt.txt \
  --output /absolute/path/output.mp4
```

### Batch Manifest Execution

For generating multiple clips or an entire scene sequence, put jobs in a JSON manifest:

```json
{
  "jobs": [
    {
      "id": "scene1",
      "title": "Opening establishing shot",
      "prompt_file": "/absolute/path/prompt1.txt",
      "model": "veo-3.1-generate-preview",
      "aspect_ratio": "16:9",
      "resolution": "1080p",
      "duration_seconds": 5,
      "output_name": "scene1"
    },
    {
      "id": "scene2",
      "title": "Character close-up",
      "reference_images": ["/absolute/path/hero.png"],
      "prompt": "Cinematic close-up of the hero speaking determinately in the rain, camera slowly zooms in. Audio: sound of rain and footsteps.",
      "model": "veo-3.1-generate-preview",
      "duration_seconds": 5,
      "output_name": "scene2"
    }
  ]
}
```

Run batch from skill directory:
```bash
python scripts/runner.py batch \
  --manifest /absolute/path/jobs.json \
  --output-dir /absolute/path/outputs \
  --progress /absolute/path/outputs/progress.json
```

5. **Verify Outputs**:
   - Confirm each output MP4 exists, is non-empty, and has valid video/audio streams.
   - Report local file paths plainly to the user.

## Operational Limits & Guidelines

- Reference images: Veo 3.1 accepts up to 3 reference images per job.
- Duration: Standard range is 5–8 seconds per generation.
- Never hardcode or print `GEMINI_API_KEY` or OAuth tokens into prompt files, manifest logs, or git commits.
- Sessions created by `batch` are automatically terminated when completed to prevent unnecessary Colab resource usage.
