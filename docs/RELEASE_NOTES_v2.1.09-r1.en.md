# Warcraft III 3.0 Trainer 2.1.09

This replaces the existing 2.1.09 download. Close the old trainer and download it again. The new build ID is **B6606E389F0B**.

- Speeds up the Batch edit tab by reusing the global selection reader and combining repeated identity binding and stat queries for the whole selection.
- Keeps every unit's editable fields. The global read button, batch writes and other features are unchanged.
- Keeps the built-in **3.0.1.24360** adapter and the previous four game-build profiles. No separate import is needed.

4,908 offline tests and 120 subtests passed (29 skipped). Matching before/after fixtures for five game builds returned the same fields; 24 units required 26 native requests instead of 96. Only the batch module changed inside the EXE, and its offline self-test passed. Actual game latency and external-machine effects have not been measured.

Updated source: [v2.1.09-r1](https://github.com/dc114154qq/war3-reforged-trainer/tree/v2.1.09-r1). The attached source ZIP contains this revision; the original v2.1.09 tag retains the initial source.
