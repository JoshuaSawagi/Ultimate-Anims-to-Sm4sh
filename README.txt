Ult2S4 - port Smash Ultimate animations to Smash 4 (Wii U)
==========================================================
The reverse of JoshuaSawagi's S4-Anims-to-Ult. Converts Ultimate animations exported from StudioSB as
Maya .anim files into Smash 4 .omo animations and writes them into the fighter's motion .pac files.

FILES
  Ult2S4 GUI.bat      double-click to open the GUI
  ult2s4_gui.py       the GUI (must stay next to ult2s4.py)
  ult2s4.py           the converter (also usable from the command line)
  install_numpy.bat   one-time setup: installs numpy

SETUP (once)
  1. Install Python 3 from https://www.python.org/downloads/ - tick "Add python.exe to PATH".
  2. Double-click install_numpy.bat.

YOU NEED
  - Ultimate animations: open the Ultimate fighter in StudioSB, load the .nuanmb, export as Maya .anim
    (all bones, every frame). Name it after the motion, e.g. a00wait1.anim, a02run.anim.
  - The Smash 4 fighter's model.vbn  (fighter\<name>\model\body\c00\model.vbn)
  - The Smash 4 fighter's motion folder (fighter\<name>\motion\body\ : main.pac, lhand.pac, rhand.pac, swing pacs)
  - Recommended: a copy of the fighter's untouched ORIGINAL motion .pac files (the "stock reference"). Once your
    motion folder holds converted moves, the skirt needs the real Smash 4 dress to measure against.

USING THE GUI
  1. Pick the skeleton (model.vbn), the motion folder and an output folder. Optionally pick the
     stock reference folder (the untouched original .pac files).
  2. "Add .anim files..." - the slot is taken from the file name. Double-click a row to pick another slot.
     "Add same file to another slot" puts one animation into two slots (e.g. Wait2 -> Wait4).
  3. Convert. The log shows what was replaced (also saved as report.txt in the output folder).
  4. "Install into motion folder..." copies the new .pac files in (old ones are backed up to .\backups\).
  5. Rebuild the patch in Sm4shExplorer and test.
  Look: Options > Theme (Windows default, Light, Dark, Midnight, Forest, Peach, Daisy) and
  "Accent color..." for any highlight colour you like. Your choice is remembered.

COMMAND LINE
  py ult2s4.py --vbn "path\model.vbn" --pacs "path\motion\body" --out out a02run.anim a00wait2.anim=A00Wait4
  Options: --skirt auto|stock|anchored|neutral|ult   (default auto)     --no-pushout     --prefix FitPeachBody
           --stock "path\original\motion\body"   (untouched stock .pacs used as the skirt reference)

SKIRT (Peach / Daisy)
  auto = Smash 4's own skirt when the legs match the stock move; Smash 4's skirt timing + push-out when the
  length matches but the legs differ; Ultimate's sway on Smash 4's skirt shape + push-out otherwise.
  neutral = auto picks this when Ultimate's baked skirt keys snap around (Ultimate simulates the skirt in
  game, so attack exports like down tilt can jump 100+ degrees in one frame): the dress holds Peach's
  standing shape and only the push-out moves it.
  For a move that differs a lot from Peach's own (more than 45 deg on the legs), the dress starts from
  Peach's standing dress (A00Wait1) instead of her version of that move.
  Push-out swings skirt panels out wherever a knee or shoe would poke through the dress. The hem is never
  lifted above where Peach's own dress reaches, so expect some leg to show in big kicks rather than a flipped skirt.

LIMITS
  - Motion .pac files are shared by every costume of the fighter.
  - Timing follows Ultimate: fine for idles/movement; attacks still use Smash 4's hitbox timing (game.bin).
  - Face expressions are not carried over (face.pac keeps Smash 4's own).
  - Victory poses live in motion\bodyresult. Smash 4's own has only main.pac + face.pac; if your folder also has
    hand/dress .pacs they're converted too (the dress starts from the standing dress in motion\body).
  - Other fighters: body and finger bones work for every fighter S4-Anims-to-Ult covers; swing bones
    (hair, capes, tails) need their names added near the top of ult2s4.py (see the U2S table).

VERSION HISTORY
  2026-10-31  Fixed "operands could not be broadcast together" crash when the reference files for a motion have
              different lengths (victory face/body, hair in down tilt or throws): they're resampled to the body's length.
              When the reference has no dress for a motion (victory poses), the standing dress (A00Wait1) is
              taken from the fighter's motion\body folder next to it.
  2026-10-31  Victory poses (motion\bodyresult): face.pac is left as is and no longer stops the conversion
              ("--skirt stock needs the same frame count"); the dress step is skipped there (no skirt file).
  2026-10-31  Stock reference folder (--stock) in GUI and command line; "neutral" skirt mode, picked
              automatically when Ultimate's skirt keys jump; hem height limit (fixes the flipped dress in
              down tilt and other kicks). Idle/dash/run results unchanged.
  2026-10-29  Themes, accent colour, push-out limits (fixes the dash skirt flip).
  2026-10-27  First GUI release.
