To use it:

In StudioSB, export each Ultimate animation as a Maya .anim file, with all bones.
Run this, using the Smash 4 fighter's model.vbn and its motion folder:
python ult2s4.py --vbn "...\fighter\peach\model\body\c00\model.vbn" --pacs "...\fighter\peach\motion\body" --out out a00wait1.anim a02run.anim
Copy the .pac files from out into the fighter's motion\body folder in your workspace.

The animation name comes from the file name, so a02run.anim replaces A02Run. To put it in a different slot, write file.anim=MotionName, for example a00wait1.anim=A00Wait2. Each run also writes a report.txt listing what was replaced.

Use a fighter's swing bones (skirts, hair, capes) on a fighter other than Peach/Daisy needs their bone names added to the short tables near the top of the script. The body and finger bones already work for any fighter the original S4-Anims-to-Ult tool covers.
