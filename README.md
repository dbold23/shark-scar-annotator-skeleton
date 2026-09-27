# Shark Scar Annotator

Multi-rater annotation of scars, pose and shape on twenty years of white shark footage.
Live for the lab at [annotate.shark-id.org](https://annotate.shark-id.org).

> **This is a skeleton.** It is the real module layout, class and function signatures and
> docstrings of a private research codebase, with every function body replaced by `...`
> and all data, weights, configuration and credentials left out. It shows how the system
> is built; it does not run. The full code is private while the work is prepared for
> publication. Copyright Daniel Sambold, all rights reserved.

![The annotation flywheel](docs/flywheel.svg)

The lab has footage from four California sites (Aptos, Año Nuevo, Point Reyes, the
Farallons) and 10 to 20 undergraduates each semester. The platform turns that attention
into labels a paper can stand on: scar boxes and types, a 16-point skeleton, a prototype 3D pin on
a shark model, scars followed across frames, and consensus that counts "I looked and
there is no scar" as a vote.

## Design choices worth reading

- **Consensus can only lower a label.** A scar three people reported and seventeen
  denied used to publish as confirmed; the dissent rule now marks it disputed
  (`annotation/database.py`, `annotation/scar_consensus.py`).
- **A blind arm is built in.** On about 15 % of annotator-frame pairs the model's hint
  is computed and withheld, so anchoring can be measured
  (`annotation/hint_blinding.py`).
- **Time is a flag, never a weight.** Effort tracking finds rushed and hard frames
  without paying anyone for speed (`annotation/effort.py`).
- **Exports are projections.** Darwin Core, COCO and signal formats are read-only
  views of one store (`annotation/dwc_adapter.py`, `annotation/signal_exports.py`).

## Stack

Flask, SQLite (WAL, foreign keys enforced), vanilla JavaScript with a WebGL scar-pin
viewer, SAM2 segmentation, YOLOv8-pose, Google OAuth, Docker behind nginx and Cloudflare.
The front end is not included in this skeleton.

## Layout

```
annotation/
segmentation/
signals/
```
