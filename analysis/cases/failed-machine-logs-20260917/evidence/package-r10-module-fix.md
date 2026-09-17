# Package verification: 2.0.3 r10

- EXE: `dist-2.0.3-3.0.0.24268-r10/War3ReforgedTrainer-v2.0.3.exe`
- FileVersion: `2.0.3.0`
- ProductVersion: `2.0.3`
- Size: `18867737` bytes
- SHA256: `CFC3C3BDAA771E59BAB5E2E577316712FC69465D883DE3E2B5DF73C3E36C1C02`
- Spec keeps `uac_admin=True`; the prior system UAC policy change remains independent of the package.

## Verified results

- `--status`: exit `0`
- `--pid 12716 --list-resources` through the elevated Windows launch path: exit `0`
- `--pid 12716 --engine-camera-probe` through the elevated Windows launch path: exit `0`
- Current game module enumeration: `152` records; selected and registry base `0x7ff636940000`.
- Regression set: `583 passed, 32 subtests passed in 26.78s`.

The external input was explicitly from `2.0.2` with `current-24268-loader-backed-native`; r10 is the current `2.0.3` package containing the filename-independent module binding and bounded startup retry.
