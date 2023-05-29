# khartes

Khartes (from χάρτης, an ancient Greek word for scroll) is a program
that allows users to interactively explore, and then segment, 
the data volumes created by high-resolution X-ray tomography of the Herculaneum scrolls.

Khartes is written in Python; it uses PyQt5 for the user interface, numpy and scikit for efficient computations,
pynrrd to read and write NRRD files (a data format for volume files), and OpenCV for graphics operations.

The main emphasis of khartes is on interactivity and a user-friendly GUI; no computer-vision or machine-learning
algorithms are currently used.

The current version is really an alpha-test version; it is being provided to get some early user feedback.

The only documentation at this point is the video below.  Note that it begins with an "artistic" 60-second
intro sequence which contains no narration, but which quickly highlights some of khartes' features.
After the intro, the video follows a more traditional format, with a voiceover and a demo.
The entire video
is about 30 minutes long.  There is no closed captioning, but the script for the video can
be found in the file demo1_script.txt.

(If you click on the image below, you will be taken to vimeo.com to watch the video)

[![Watch the video](https://i.vimeocdn.com/video/1670955201-81a75343b71db9c84b6b4275e3447c943d2128ab8b921a822051046e83db0c96-d_640)](https://vimeo.com/827515595)

## Vacation announcement

I will be unavailable to work on khartes from the end of May until the
end of June.  I will try to monitor the Vesuvius Scrolls Discord server,
but I cannot guarantee that I will be able to fix bugs or answer questions
during that time.  But my availability in July looks good!

## Installation

In theory, you should be able to run simply by
cloning the repository, making sure you have the proper dependencies 
(see "anaconda_installation.txt" for a list), and then typing `python khartes.py`.  

When khartes starts, you will see some explanatory text on the right-hand side of the interface 
to help you get started.  This text is fairly limited; you might want to watch the video above to get a better
idea how to proceed.

A couple of notes based on early user testing (**you might
want to review these again** after using khartes for the first
time):

The `File / Import TIFF Files...` menu option
creates a khartes data volume
by reading TIFF files that you already have somewhere on disk.
You simply need to point the import-TIFF dialog to the folder
that contains these files.

The import-TIFF function uses more memory than it should 
(it unnecessarily duplicates the data volume in memory during
the import process).  This means that at the current time you
should be sparing of memory, creating data volumes that are no
larger than half the size of your physical memory,
if you want to avoid memory swapping.

## General workflow

As the programmer, I know how khartes works internally.  However,
I only have a few hours experience as a user of the software.
The advice that follows is based on this experience, but 
thes suggestions
should not be treated as something engraved in stone, more
like something written in water-based ink on papyrus.

**Step 0**, before you start working,
is to choose the area to segment.  For your first
attempt, you should start with a sheet that is clealy separated
from its neighbors; no need to dive into the deep end.
For your next attempt, you mighgt want to start with a sheet
that is separated on one side.  Keep in mind that after you
have created a fragment for one sheet, you can view that fragment
even while working on the next sheet, as a kind of guide.
So one strategy is to work on a series of sheets that are 
parallel to
each other, starting with the easiest.

**Step 1** is to start in an easy area, picking some points
on the inline (top window) and crossline (middle window) slices.
This will create a diamond-shaped area in the fragment viewer
(right-hand window).  Make sure you are happy with what you see
before expanding.

**Step 2**, expand by alternating between picking lines in the
inline

[work in progress...]

When you create fragments, pay attention to the triangulation
that is shown in the fragment window on the right.  Khartes'
interpolation algorithm can become erratic in areas of long,
skinny triangles, so it is a good idea to distribute enough
fragment nodes throughout the fragment, to keep the triangles
more regular.  

Another reason for monitoring the shapes of your triangles is to
improve speed of interaction.  Every time a fragment node is moved
or added, khartes updates the fragment window to reflect these changes.
This means that triangles near the modified node, and the pixels
that these triangles encompass, need to be recomputed
and redrawn.  The bigger the triangles, the longer the recomputations
take.  If a node is surrounded by large triangles that cover most
of the data volume, each change may require several seconds to recompute,
meaning that khartes no longer feels interactive.  You can prevent this problem
by keep your triangles regular and local.

So when segmenting, start in the center of a fragment
and work your way out, keeping a fairly regular mesh, instead
of trying to create a huge surface first thing.  This practice
will also make it less likely that you stray onto the wrong
sheet of the scroll in difficult areas.

Remember that khartes does not have auto-save; use Ctrl-S on
a regular basis to save your latest work.

## Exporting fragments

Khartes allows you to export your fragments to `vc_render` and `vc_layers_from_ppm`.

To export your fragment:

1. Make sure your fragment is active, that is, that it is visible
in the right-hand window.
2. In the File menu, select `Export file as mesh...`.

This will create a .obj file, which contains a mesh representing your
fragment.

You can import this mesh directly into `vc_render`.  Here is how.

First, you need to make sure you know where the following files and
directories are located:

- Your .volpkg folder, the one that contains the TIFF files that you
imported into khartes
- If your .volpkg directory contains more than one volume, you need
to know the number of the volume that contains the TIFF files
that you used.
- The .obj mesh file that you just created
- The directory where you want to create a .ppm file, and the name
that you want to give the .ppm file.  The .ppm file is needed by
`vc_layers_from_ppm`.

So the command you want to type will look something like:
```
vc_render -v [your volpkg directory] --input-mesh [your .obj file] --output-ppm [the name of the ppm file you want to create]
```
You might need to use --volume to specify your volume as well, if your volpkg has more than one.

As already mentioned, the .ppm file that `vc_render` creates can be used in `vc_layers_from_ppm` to create a 
flattened surface volume.


## Things to fix

When the user exits khartes
or reads another project, khartes does not warn the
user if there is unsaved data.

There is no way for the user to delete nodes (my usual practice
at the moment is to move them out of the way to somewhere harmless).

There is no undo function.

Memory usage during import-TIFFs (and perhaps other operations)
needs to be optimized, to allow bigger data volumes.

Allow the user to change fragment and volume names.

Allow the user to change display settings such as node size and
crosshair thickness.

The scale bar is based on a voxel spacing of 7.9 um; allow the user to 
change this.

(Many others too uninteresting to list here)
