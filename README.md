# regulations-xml-parser

[![Build Status](https://travis-ci.org/cfpb/regulations-xml-parser.svg)](https://travis-ci.org/cfpb/regulations-xml-parser)

Part of [eRegulations](http://eregs.github.io/eRegulations/).

Parse [regulation XML](https://github.com/cfpb/regulations-schema) to
generate JSON for [regulations-core[(https://github.com/cfpb/regulations-core) 
to serve to [regulations-site](https://github.com/cfpb/regulations-site).


## Usage

There are two types of RegML files:

- `regulation` files which contain the full text of a regulation version
- `notice` files which contain the changes necessary to transform the
  preceding version of a regulation into the next version

### Generating RegML from eCFR

To generate RegML from an eCFR XML file using 
 [regulations-parser](https://github.com/cfpb/regulations-parser):

```shell
./regml.py ecfr 12 [eCFR File]
```

This will generate the RegML `regulation` tree for the initial version
and RegML `notice` trees with the necessary changeset for each
subsequent version.

If you want only want to output RegML for a single notice:

```shell
./regml.py ecfr 12 [eCFR File] --only-notice [notice number]
```

## Generating RegML from `regulation` + `notice`


To apply a `notice` file to a `regulation` file:

```shell
./regml.py apply [RegML regulation file] [RegML notice file]
```

This will create a new RegML file with the notice file's changes applied
to the given regulation file.

## Validating RegML

To validate a RegML file against
[regulations-schema](https://github.com/cfpb/regulations-schema):

```shell
./regml.py validate [RegML regulation or notice file]
```

## Generating JSON from RegML

To generate JSON from RegML for use with
[regulations-core](https://github.com/cfpb/regulations-core):

```shell
./regml.py json [RegML regulation file] []RegML regulation file] ...
```

If more than one RegML file is given, the JSON files that are created
will include diff files that contain the changes between each version
provided.

