# Changelog
All notable changes to this project will be documented in this file.

The format is based roughly on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.13.1] - 2022-01-29
### Added
- Run tests on Python 3.9 and default to that for linting, etc.

### Fixed
- Raise UNIMPLEMENTED instead of UNKNOWN when no handler is found for a method (thanks Richard Mahlberg!)

## [0.13.0] - 2020-12-27
### Added
- Client-side interceptors (thanks Michael Morgan!)

### Changed (breaking)
- Added a `context` parameter to special case functions in the `testing` module

### Fixed
- Build issue caused by [pip upgrade](https://github.com/cjolowicz/hypermodern-python/issues/174#issuecomment-745364836)
- Docs not building correctly in nox

## [0.12.0] - 2020-10-07
### Added
- Support for all streaming RPCs

## [0.11.0] - 2020-07-24
### Added
- Expose some imports from the top-level

### Changed (breaking)
- Rename to `ServerInterceptor` (do not intend to make breaking name changes after this)

## [0.10.0] - 2020-07-23
### Added
- `status_on_unknown_exception` to `ExceptionToStatusInterceptor`
- `py.typed` (so `mypy` will type check the package)

### Fixed
- Allow protobuf version 4.0.x which is coming out soon and is backwards compatible
- Testing in autodocs
- Turn on xdoctest
- Prevent autodoc from outputting default namedtuple docs

### Changed (breaking)
- Rename `Interceptor` to `ServiceInterceptor`

## [0.9.0] - 2020-07-22
### Added
- The `testing` module
- Some helper functions
- Improved test coverage

### Fixed
- Protobuf compatibility improvements

## [0.8.0] - 2020-07-19
### Added
- An `Interceptor` base class, to make it easy to define your own service interceptors
- An `ExceptionToStatusInterceptor` interceptor
