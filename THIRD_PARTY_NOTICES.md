# Runtime and CI attribution

No third-party Python package is required or vendored.

| Component | Use | License/source |
| --- | --- | --- |
| Python 3.11 standard library | Installed interpreter/runtime | [PSF license and notices](https://docs.python.org/3.11/license.html) |
| SQLite bundled with Python | Local snapshot and workflow state | [Public domain](https://sqlite.org/copyright.html) |
| actions/checkout v7.0.1 | CI-only checkout, pinned commit | [MIT license](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE) |
| actions/setup-python v7.0.0 | CI-only selected Python runtime | [MIT license](https://github.com/actions/setup-python/blob/5fda3b95a4ea91299a34e894583c3862153e4b97/LICENSE) |

The workflow references these actions; their source is not vendored. Beancount is linked as GPL-2.0 prior art only and is not a dependency. There are no bundled model weights, SDKs, paid services or third-party datasets.
