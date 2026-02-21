---
name: video-frames
description: "Extract frames, thumbnails, or clips from video files using ffmpeg. Use when analyzing video content or creating previews."
---

# Video Frames

Extract frames, thumbnails, and clips from video files.

## When to Use

- "Extract a frame from this video"
- "Create a thumbnail for this video"
- "Get frames at 1fps from this clip"
- "Cut a segment from this video"
- Analyzing video content by extracting key frames

## Extract a Single Frame

```bash
ffmpeg -i input.mp4 -ss 00:00:05 -frames:v 1 frame.png
```
`-ss 00:00:05` = seek to 5 seconds.

## Extract Frames at Interval

```bash
ffmpeg -i input.mp4 -vf "fps=1" frames_%04d.png
```
`fps=1` = one frame per second. Use `fps=1/10` for one every 10 seconds.

## Create a Contact Sheet (Grid of Frames)

```bash
ffmpeg -i input.mp4 -vf "fps=1/30,scale=320:-1,tile=4x4" contact_sheet.png
```
One frame every 30 seconds, 4x4 grid.

## Cut a Video Segment

```bash
ffmpeg -i input.mp4 -ss 00:01:00 -to 00:02:00 -c copy clip.mp4
```

## Get Video Info

```bash
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4
```

## Extract Audio

```bash
ffmpeg -i input.mp4 -vn -acodec mp3 audio.mp3
```

## Convert Format

```bash
ffmpeg -i input.webm -c:v libx264 output.mp4
```

## Notes

- ffmpeg and ffprobe are available as execute commands
- Always use `-y` flag to overwrite output files without prompting
- For large videos, use `-ss` before `-i` for faster seeking
- Output files are saved in the workspace directory
