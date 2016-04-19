# regulations-xml-parser

[![Build Status](https://travis-ci.org/cfpb/regulations-xml-parser.svg)](https://travis-ci.org/cfpb/regulations-xml-parser)

Part of [eRegulations](http://eregs.github.io/eRegulations/). 

Parse [Regulation XML](https://github.com/cfpb/regulations-schema) to
generate JSON for [regulations-core](https://github.com/cfpb/regulations-core)
to serve to [regulations-site](https://github.com/cfpb/regulations-site).

A full development envinronment to perform all of these tasks can be set up using [regulations-bootstrap](https://github.com/cfpb/regulations-bootstrap).

## Usage

There are two types of RegML files:

- `regulation` files which contain the full text of a regulation version
- `notice` files which contain the changes necessary to transform the
  preceding version of a regulation into the next version

### Generating RegML from eCFR

Scenario: *You have a regulation and no RegML and you need to generate 
the entire RegML history for that regulation.*

To generate RegML from an eCFR XML file using
 [regulations-parser](https://github.com/cfpb/regulations-parser):

```shell
./regml.py ecfr parse-all [CFR title number] [eCFR file]
```

This will generate the RegML `regulation` tree for the initial version
and RegML `notice` trees with the necessary changeset for each
subsequent version of the regulation based on notices published in the 
Federal Register.

### Generating RegML from a single eCFR Notice

Scenario: *You have a regulation and a body of RegML for its history, 
but a new final notice was published in the Federal Register.*

To generate RegML from a single eCFR XML notice, you need to have a 
RegML `regulation` file for the immediately prior notice. 

```shell
./regml.py ecfr parse-notice [CFR title number] [CFR part number] [notice document number] --applies-to [prior notice document number]
```

This will generate the RegML `notice` changeset for the new notice. 
That changeset can then be applied as described below to generate the 
RegML `regulation` file.

## Generating RegML from `regulation` + `notice`


To apply a `notice` file to a `regulation` file:

```shell
./regml.py apply-notice [RegML regulation file] [RegML notice file]
```

This will create a new RegML file with the notice file's changes applied
to the given regulation file.

The path to the RegML files can be relative to the `XML_ROOT` in your
`settings.py` file. For example, if you have the RegML files in
`../../regulations-stub/xml` and your
`XML_ROOT="../../regulations-stub/xml"`, you can use:

```
./regml.py apply-notice 1111/1234-56789.xml 1111/1234-67890.xml
```

## Validating RegML

To validate a RegML file against
[regulations-schema](https://github.com/cfpb/regulations-schema):

```shell
./regml.py validate [RegML regulation or notice file]
```

## RegML Sanitization

Some utilities to sanitize RegML are also included


### Term Finder

The term finder prompts the user to place references to defined terms
wherever they may be found. These corrections can then be writen back to
the original RegML file.

```shell
./regml.py check-terms [RegML regulation file]
```

`check-terms` also takes an optional label, which will cause it to only
operate on that particular part of the regulation (useful for large
regulations). For example:

```
./regml.py check-terms 1026/2011-31715 --label 1026-1
You appear to have used the term "Credit" in 1026-1-a without referencing it:
<content xmlns="eregs">...</content>

Would you like the automatically fix this reference in the source?
(y)es/(n)o/(i)gnore this term/(a)lways correct:
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

As with the other RegML commands above, the path to the RegML files
can be relative to the `XML_ROOT` in your `settings.py` file.
For example, if you have the RegML files in
`../../regulations-stub/xml` and your
`XML_ROOT="../../regulations-stub/xml"`, you can use:

```
./regml.py json 1111/1234-56789.xml
```

Additionally, to generate JSON for all RegML files in a particular
regulation's directory in the `XML_ROOT`, you can simple use the
regulation directory name (usually the part number):

```
./regml.py json 1111
```
