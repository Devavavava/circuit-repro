Cached xschem symbol-library files used only as *tooling* by `xschem_flatten.py`
to read pin geometry (device kind + pin coordinates) -- not circuit data being
cataloged, analogous to using ngspice itself or a PDK's device models to run a
simulation. Two license families, kept apart here:

- `sg13g2_pr__*.sym` -- from `IHP-GmbH/IHP-Open-PDK`, **Apache-2.0**.
- `iopin.sym`, `ipin.sym`, `opin.sym`, `lab_wire.sym` -- from
  `StefanSchippers/xschem`'s bundled generic device library, **GPL-2.0**
  (per each file's own header).

Do not mistake these for Apache-2.0-licensed circuit content -- they are
xschem/PDK tooling artifacts fetched on demand by `xschem_flatten.py`
(`SymbolLoader`) and cached here to avoid repeat GitHub fetches.
