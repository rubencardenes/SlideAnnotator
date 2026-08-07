# CHANGELOG

<!-- version list -->

## v1.11.0 (2026-08-07)

### Code Style

- **review_window**: Fixed ruff format
  ([`978b0e1`](https://github.com/rubencardenes/SlideAnnotator/commit/978b0e14a966723ef5c88a69102bb1b9fd7139f8))

### Features

- **fov-tool**: Add FOV placement tool and sync FOVs folder on save
  ([`cd262f4`](https://github.com/rubencardenes/SlideAnnotator/commit/cd262f455150eeb3c6c309bd9460cc32aefc9b08))

- **review-window**: Channel-max slider bounds, train/test filter, marker edit
  ([`db169ad`](https://github.com/rubencardenes/SlideAnnotator/commit/db169ad67ecd9ad61997019ae3de5a1435796315))


## v1.10.0 (2026-07-24)

### Documentation

- Update README for latest changes and add app screenshot
  ([`0d824ac`](https://github.com/rubencardenes/SlideAnnotator/commit/0d824ac7e1c62688f8b8e4831422a8422466de55))

### Features

- **regions**: Merge touching regions and punch holes
  ([`77c3027`](https://github.com/rubencardenes/SlideAnnotator/commit/77c302713185046b23f3d95023d448bb290c0767))


## v1.9.0 (2026-07-16)

### Code Style

- Ruff format
  ([`a46f361`](https://github.com/rubencardenes/SlideAnnotator/commit/a46f3614bd16868d099c7d7ad5e7d76491d778ba))

### Features

- Adapted ONNX inference to deal with more normalization schemes
  ([`da59849`](https://github.com/rubencardenes/SlideAnnotator/commit/da5984945503e97b8b324fd423ce0aedee7c5294))

- **inference**: Add RF-DETR cell detector support
  ([`8a29c49`](https://github.com/rubencardenes/SlideAnnotator/commit/8a29c499d3ba76cdde903e1d247ab752d7f094cd))

- **ui**: Make evaluations table sortable, filterable, and editable
  ([`c212d8f`](https://github.com/rubencardenes/SlideAnnotator/commit/c212d8f530eb1417ce5b8885a76ab63196ba8e2f))


## v1.8.0 (2026-07-14)

### Features

- **eval**: Filter markers/images by train/test group + refresh DB paths
  ([`ddc9092`](https://github.com/rubencardenes/SlideAnnotator/commit/ddc9092b87e460434622540c09706377c739184f))


## v1.7.0 (2026-07-14)

### Bug Fixes

- **ciz_slide_reader**: Fixed problem with czi reader, support for RGB
  ([`85daedb`](https://github.com/rubencardenes/SlideAnnotator/commit/85daedb4a46c46b9a40557db7dd575031ff8e57c))

### Features

- **ui**: Split image panel into Train/Test sections
  ([`e5a9550`](https://github.com/rubencardenes/SlideAnnotator/commit/e5a9550f7b5c3dabded0c5d8c6002f481d76158c))


## v1.6.0 (2026-07-13)

### Features

- Evaluate ONNX models against annotations + app icon
  ([`1c2b5be`](https://github.com/rubencardenes/SlideAnnotator/commit/1c2b5be81bb82b04ec85cde301abc3fded386eca))


## v1.5.1 (2026-07-05)

### Bug Fixes

- **inference**: Lazily import the stardist2d C extension
  ([`df5dc9d`](https://github.com/rubencardenes/SlideAnnotator/commit/df5dc9dbb9f411d81c270c63f1ef3531a5d56c1b))

### Continuous Integration

- Add pytest smoke tests and harden CI/CD pipeline
  ([`66cbf7b`](https://github.com/rubencardenes/SlideAnnotator/commit/66cbf7b538943b0d1b5734ec8e257c59cf08bcb0))


## v1.5.0 (2026-07-03)

### Bug Fixes

- **colors**: Cycle fallback channel colors instead of repeating gray
  ([`7522f50`](https://github.com/rubencardenes/SlideAnnotator/commit/7522f505108f34ca3b98b73bbf15684fdb13d5ff))

### Features

- Added progress bar fixed channel colors
  ([`3a5e91e`](https://github.com/rubencardenes/SlideAnnotator/commit/3a5e91efaf602a88603025081662419a8ac1decb))


## v1.4.0 (2026-07-02)

### Features

- **serializer**: Adding feature to export annotations in COCO format
  ([`c980e54`](https://github.com/rubencardenes/SlideAnnotator/commit/c980e54834a3dff9bb29369211ebc0a242ae0a56))


## v1.3.0 (2026-06-26)

### Code Style

- Fixed linting
  ([`71a4e02`](https://github.com/rubencardenes/SlideAnnotator/commit/71a4e0260b7482d255e64124873d05a4a078cad6))

### Continuous Integration

- Fixed dependency from DBAgentquery
  ([`7f543d2`](https://github.com/rubencardenes/SlideAnnotator/commit/7f543d2175881d5a5c9de36b8af0121acf948ebc))


## v1.2.0 (2026-06-18)

### Code Style

- Ruff format
  ([`3560806`](https://github.com/rubencardenes/SlideAnnotator/commit/35608065d2f6855b16b996f0013b7d5ad4ccad37))

- **settings**: Reorder config keys and use flow-style vectors
  ([`771e546`](https://github.com/rubencardenes/SlideAnnotator/commit/771e546232aebcfbc3c4ed6b7cdbda30b29e7b9c))

### Features

- Interaface changes
  ([`15c91fc`](https://github.com/rubencardenes/SlideAnnotator/commit/15c91fc2d8c2d12e94b555db78016a18988e25c9))

- **settings**: Replace StarDist-only dialog with full settings editor
  ([`457ad1b`](https://github.com/rubencardenes/SlideAnnotator/commit/457ad1b082a6ccd21dd3b6d4cb2d8375f44efe8f))


## v1.1.0 (2026-06-15)


## v1.0.0 (2026-06-15)

- Initial Release
