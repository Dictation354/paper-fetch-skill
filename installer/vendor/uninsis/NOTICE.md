# UninsIS.dll provenance

The vendored `i386/UninsIS.dll` is the 32-bit setup-time helper from the
official UninsIS 1.7.0 release:

- Upstream: <https://github.com/Bill-Stewart/UninsIS>
- Release: <https://github.com/Bill-Stewart/UninsIS/releases/tag/v1.7.0>
- Release commit: `adcaa752eb85d518ba55138e196948adc87e5a51`
- Release archive: `UninsIS-1.7.0.zip`
- Archive SHA-256: `8004d12b1635ccb7fba0c6aa0aeeb72871f9d50aa02d7b8f3134dc10feca4994`
- `i386/UninsIS.dll` SHA-256: `9bf8badad59783459f85a1e6203f0c8257bb9554927ca2fa6df5f74850bdcf78`
- License: GNU Lesser General Public License v3 or later
  (`LGPL-3.0-or-later`); see `LICENSE`.

Inno Setup 6 uses a 32-bit setup process even when the installed application
uses 64-bit install mode, so the official i386 helper is the applicable build.
It is loaded only while Setup runs and is not copied into the application
runtime. The license and this provenance notice are installed under
`licenses/` for redistribution with the Windows installer.
