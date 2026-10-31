# Ultimate -> Smash 4 animation porter (ult2s4)

The reverse of JoshuaSawagi's S4-Anims-to-Ult. Needs Python 3 and numpy.

## Use
1. In StudioSB, open the Ultimate fighter model with its .nuanmb animations and export each one as Maya `.anim` (all bones).
2. Run:
   `python ult2s4.py --vbn <S4 fighter>/model/body/c00/model.vbn --pacs <S4 fighter>/motion/body --out out a00wait1.anim a02run.anim ...`
   - The motion name comes from the file name (a02run -> A02Run). Override it with `file.anim=MotionName`.
   - Every .pac in `--pacs` (main, lhand, rhand, swing pacs) gets its own .omo for that motion.
3. Copy `out/*.pac` into `workspace/content/patch/data/fighter/<name>/motion/body/`.

## How it works
- Bone names: the reverse of the original tool's S4->Ult table, plus HaveL/R, Throw, Trans, Rot, Hip and the Peach/Daisy swing bones.
- Ultimate's extra bones ClavicleC and LegC are folded back in:
  - LShoulderN = ClavicleC * ClavicleL
  - LLegJ = LegC * LegL
  - (same for the right side)
- Rotations: .anim euler in radians, R = Rz*Ry*Rx. This was verified because Daisy's Ultimate dash converts to within about 0-5° of stock Smash 4 Peach's dash.
- Frames: Ultimate key frames 1..N, which is the same count Smash 4 uses. StudioSB's endTime is N+1.
- Each .omo contains exactly the bones the stock .omo in that pac animates. Bones Ultimate doesn't have keep their stock motion, stretched to the new length.
- Face bones are skipped (Smash 4 body animations don't key them).
- The .omo writer is the Forge-layout one already proven in game. The .pac writer reproduces stock pacs byte-for-byte.

## Limits
- **Skirt (Peach/Daisy):** Ultimate rebuilt the skirt rig, so its rotations are applied on Smash 4's bone lengths. The top ring matches well (10-25°); the lower segments are approximate.
- **Timing:** only idle/loop or movement animations are safe. For attacks, the converted frame count and pose timing follow Ultimate, but Smash 4's game.bin hitboxes still follow the Smash 4 timing.
- **Shared .pac:** motion pacs are shared by every costume slot of the fighter.
- **Other fighters:** need their own swing-bone names added to the tables at the top of ult2s4.py. The main/hand bones work for any fighter the original tool covers.

## Test run: Daisy (Ultimate) onto Peach (Smash 4), 2026-10-30
- Converted: A00Wait1 (236 frames, stock 101), A00Wait2 (94, stock 240), A00Wait3 (130, stock 270), A02Dash (35), A02Run (33).
- The waits are Daisy's own idles, so they differ from Peach's. Loops close cleanly (the first and last frames match).
- Stock pacs are in `extract/data/fighter/peach/motion/body/`; the workspace copies were identical to stock.
