# Google SynthID Image Benchmark — Results

- detector: **mock / mock-vertex-imagen**
- sources: **2** | rows: **44** | price/call: $0.0 | estimated total: **$0.0**

> Verifier is offline (mock / unavailable). Detection columns are placeholders; only transform quality metrics below are meaningful until the real Vertex verifier is run.

## Transform quality (mean over sources)

| transform | SSIM | PSNR | mean width | mean size (B) | runtime (ms) | n |
|---|---|---|---|---|---|---|
| crop_0.5 | 0.921 | 13.94 | 128 | 618 | 0.5 | 2 |
| crop_0.25 | 0.952 | 19.15 | 192 | 1172 | 0.5 | 2 |
| crop_0.1 | 0.975 | 25.10 | 230 | 1610 | 1.0 | 2 |
| bc_b0.9_c1.1 | 0.983 | 25.64 | 256 | 3037 | 6.9 | 2 |
| chain_png_jpeg_webp | 0.985 | 32.02 | 256 | 1768 | 22.6 | 2 |
| jpeg_q50 | 0.985 | 31.75 | 256 | 4457 | 1.4 | 2 |
| convert_webp | 0.987 | 33.90 | 256 | 1811 | 30.1 | 2 |
| bc_b1.0_c1.1 | 0.992 | 31.61 | 256 | 2314 | 1.8 | 2 |
| convert_jpeg | 0.992 | 33.35 | 256 | 4442 | 3.4 | 2 |
| jpeg_q75 | 0.992 | 33.35 | 256 | 4442 | 0.9 | 2 |
| bc_b1.1_c1.0 | 0.993 | 25.84 | 256 | 2281 | 3.1 | 2 |
| jpeg_q85 | 0.993 | 34.00 | 256 | 4534 | 1.5 | 2 |
| resize_0.5 | 0.994 | 35.25 | 128 | 811 | 4.5 | 2 |
| jpeg_q95 | 0.997 | 34.57 | 256 | 4412 | 0.5 | 2 |
| resize_0.75 | 0.998 | 38.49 | 192 | 1755 | 2.5 | 2 |
| resize_1.5 | 0.999 | 41.67 | 384 | 4531 | 0.0 | 2 |
| convert_png | 1.000 | 100.00 | 256 | 1925 | 5.5 | 2 |
| screenshot_x1 | 1.000 | 100.00 | 256 | 1925 | 0.0 | 2 |
| screenshot_x10 | 1.000 | 100.00 | 256 | 1925 | 28.2 | 2 |
| screenshot_x2 | 1.000 | 100.00 | 256 | 1925 | 6.2 | 2 |
| screenshot_x5 | 1.000 | 100.00 | 256 | 1925 | 14.2 | 2 |

## Verifier status counts (after transform)

| status | count |
|---|---|
| MOCK | 44 |

## Notes

- SSIM/PSNR for geometry-changing transforms (resize/crop) are computed after resizing back to the source dimensions — approximate perceptual similarity.
- `estimated_api_cost_usd` is per-row `price_per_call × calls`; 0 under the mock.
