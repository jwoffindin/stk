<div id="top"></div>
<!-- From https://github.com/othneildrew/Best-README-Template/ -->



[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<br />
<div align="center">
  <a href="https://github.com/jwoffindin/stk">
    STK
  </a>

<h3 align="center">STK - Opinionated CloudFormation Deployments</h3>

  <p align="center">
    A "better" (well, opinionated at least) approach to managing AWS infrastructure with CloudFormation.</p>
</div>


<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

STK provides an opinionated framework for managing AWS infrastructure with CloudFormation.

The two key benefits of using `stk` for CloudFormation management.

* Decouple CloudFormation templates from configuration. This simplifies multi-environment and allows you to build up a library of reusable components.
* Reduce change risk through improvded visibility. Use of Jinja2 for templates and use of explicit configuration (directly interpolated variables) over implicit configuration (AWS parameters) (more later) mean you can see exactly what is going to change.
### Local installation (Python/Pip)

Requires python 3.10+

    # Install STK via pip
    pip install git+https://github.com/jwoffindin/stk.git

### Docker

    alias cfn="docker run --rm -it -v ~/.aws:/root/.aws -v ~/.ssh:/root/.ssh -v $TEMPLATE_PATH:/templates -v $CONFIG_PATH:/config johnwo/stk:latest"


<p align="right">(<a href="#top">back to top</a>)</p>


## Getting started

Quick start:

    # Deploy a stack
    stk create sns dev



### Concepts

## Commands

A full list of commands are available by running `stk help`

The most common commands:

* show-config
* show-template
* validate
* diff
* create — deploy a new stack `cfn create <archetype> <environment>`
* update - update an existing stack `cfn update <archetype> <environment>`
### Configuration file

A configuration file is simply a YAML file used to that declares:

* How we deploy a CloudFormation template into an AWS account.
* Any configuration required for the template.

A minimal template may look like:

```yaml
# $CONFIG_PATH/foo.yml
aws:
  region: ap-southeast-2
  cfn_bucket: my-bucket-for-cloudformation-deployments

environments:
  dev:
  test:
  prod:
```

This configuration file will allow us to deploy dev, test and prod instances of a CloudFormation template
`foo.yaml` into the `ap-southeast-2 `region.

```sh
# Will create a stack called foo-dev in ap-southeast-2 using default profile and/or environment
# credentials.
$ stk create foo dev

# Create and apply a change set to the 'foo-test' stack in ap-southeast-2 region.
$ stk update foo test
```

### CloudFormation Templates

The CloudFormation templates are YAML (JSON may work, I've not tried it)

The templates are processed using `Jinja2` and any variables declared in `vars:` section of a config file are available.

For example:

```yaml
# $CONFIG_PATH/foo.yml
...
vars:
  greeting: Hello World!
...
```

the corresponding template may look like:

```yaml
# $TEMPLATE_PATH/foo.yaml
Description: |
  I'd like to say {{ greeting }}, to you all
```

To avoid confusion between YAML comments and Jinja2 block level operations, we use a `##` for Jinja2. For example, if we want to allow `greeting` to be optional:

```yaml
# $TEMPLATE_PATH/foo.yaml

## if greeting is defined
Description: |
  I'd like to say {{ greeting }}, to you all
## endif

```


## Configuration

### Structure

The top-level keys that can be declared in a configuration files are:

```yaml
# Include other configuration. Allows composition and sharing of common configuration
# Two common use cases — (1) environment specific configuration, and (2) deploying multiple stacks
# from the same template
includes:

# Where to find the CloudFormation template. Supports local files, local git repositories
# or remote git repositories.
template:

# AWS Parameters that are passed into a stack. Minimize if possible, use `vars` instead.
# Good use cases include:
# * passing secrets
# * (that's about it?)
params:

# Jinja2 variables/values passed to the template. Preferred way to manage configuration - e.g.
# use template conditions rather than 'native' AWS Template Conditions - they are unwieldy and
# can make changes hard to reason about.
vars:

# References to other stacks. E.g. feeding in outputs from another stack into this one.
refs:

# Tags that are applied to the stack (and thus resources within the stack)
tags:

# Information about the AWS account being deployed into. At a minimum needs region and
# s3 bucket for uploading deployment artifacts.
aws:

# If deploying into multiple environments, any environment-specific configuration goes here.
# You need to declare at least one environment in a top-level configuration file.
environments:

# Custom helper functions may be used by templates. Since we're injecting code into our runtime, the
# configuration file must explicitly declare any helpers here.
helpers:

# Configuration that changes behavior of the 'stk' application rather configuration/template
# deployment.
core:
```

### Interpolation

Configuration values can also include Jinja2 interpolation (although the file itself is *not* a Jinja template). Many
patterns are stolen from Ansible, so some concepts may be familiar if you've used Ansible.

For example:

```yaml
# $CONFIG_PATH/foo.yml
aws:
  cfn_bucket: my-bucket-for-{{ environment }}-cloudformation-deployments
```

Declares a different bucket per tier.

### Configuration Hierarchy

Obviously, providing deploying the same template into dev, test, and production is not overly useful. We need to be
able to deploy environment-specific configuration to each stack.

Under each environment (e.g. `environments` -> `dev`), we can apply almost all the top-level configuration items to
override the defaults.

For example:
```yaml
vars:
  foo: fiz

environments:
  dev:
    vars:
      foo: fuz
  test:
  prod:
```

In this example, `foo` is `fuz` for development deployments, and `fiz` for test and prod.

Most configuration options can have environment specific overrides.

For example:

```yaml
environments:
  dev:
    aws:
      region: ap-southeast-2
    template:
      version: # use version from working directory
  test:
    aws:
      region: us-east-1
    template:
      version: main
```

<p align="right">(<a href="#top">back to top</a>)</p>

## Configuration Detail

### `includes:`

Include other configuration files.

Allows composition and sharing of common configuration to reduce unnecessary duplication.

It is a list of YAML files loaded from `includes/` directory.

They are listed in highest-to-lowest precedence.

```
# sample.yml
includes:
  - a
  - b

# includes/a.yml
vars:
  foo: 'a'

# includes/b.yml
vars:
  foo: 'b'
```

in this example, the `foo` var will be given the value `a`.

Two common use cases for include files are:

1. Environment specific configuration - e.g. AWS account details
1. Where multiple archetype files use the sample template.

### `template:`

Defines where to find the CloudFormation template. Supports local files, local git repositories
or remote git repositories.

#### Plain filesystem (not git)

If `version` is not set, then the templates are assumed to come from local filesystem - useful
when developing templates. In this case, set `root` to path.

E.g.

    environments:
      dev:
        template:
          version:
          root: ../stk-templates

You can use an environment variable to allow over-riding of template location with something like:

    environments:
      dev:
        template:
          version:
          root: {{ environ['TEMPLATE_PATH'] | default)'../stk-templates') }}

#### Git

Similar to above, but uses current commit `HEAD` in local filesystem:

    environments:
      dev:
        template:
          version: HEAD
          repo: {{ environ['TEMPLATE_PATH'] | default('../stk-templates') }}

Remote repositories are also supported. For example, the following will use current main
of github repository:

    template:
      version: main
      repo: git@github.com:jwoffindin/stk-templates.git


### `params:`

AWS Parameters that are passed into a stack. Minimize if possible, use `vars` instead.
Good use cases include:

* passing secrets
* (that's about it?)

### `vars:`

Jinja2 variables/values passed to the template.

Preferred way to manage configuration - e.g. use template conditions rather than 'native' AWS Template Conditions - they are unwieldy and can make changes hard to reason about.


### `refs:` - Referencing other stack outputs

Use the `refs:` section to retrieve outputs from other stacks.

For example, if you have another stack deployed which you need to
retieve values from (e.g. subnet IDs from a VPC stack), you can
do something like:

```yaml
refs:
  vpc:

vars:
  subnets: "{{ refs.vpc.Subnets }}"
```

will pass in a list of subnets to the template.

#### Optional references

Some stacks may be optional. A referenced output will return nil/blank value
if the stack doesn't exist.

For example:

```yaml
refs:
  an_optional_stack:
    optional: True

vars:
  some_optional_var: "{{ refs.an_optional_stack.SomeOutput }}"
```

in this case, `some_optional_var` will be set iff the referenced stack exists, otherwise it is set to `nil`.

#### Overriding stack names

Normally, external stack will found using standard `stk` naming convention (`$environment-$stack_name`).

You can override this when needing to reference a stack that does not
follow this convernsion using the `stack_name` attribute.

Like all `refs:` settings, you can set this on a per-environment basis if required:

```yaml
environments:
  prod:
    vars:
      foo: "{{ refs.some_stack.OtherOutput }}"
    refs:
      some_stack:
        stack_name: "some-weirdly-named-stack"
```

### `tags:`
Tags that are applied to the stack (and thus resources within the stack)

### `aws:`

Information about the AWS account being deployed into. At a minimum needs region and
s3 bucket for uploading deployment artifacts.

### `environments:`

If deploying into multiple environments, any environment-specific configuration goes here.
You need to declare at least one environment in a top-level configuration file.

Each sub-key of `environments` is the environment name.

Within a configuration file, environment-specific values take precedence over top-level configuration.

For example:

```
vars:
  a: 'foo'

environments:
  dev:
    vars:
      a: 'bar'
  test:
  prod:
```

In this case, a dev deployment `a` has value `bar`, and test/prod deployments `a` will value the value `foo`.

The following sections can have environment-specific overrides:

* `vars`
* `params`
* `aws`
* `refs`
* `tags`

#### Valid deployment environments

Within an archetype (top-level config) file, `environments` defines the allowable deployment
environments. Environments defined in include files are not used for this purpose.

In the following example, `a` can only be deployed as `dev` and `prod`, whereas `b` supports
`dev`, `test` and `prod` as deployment environments:

    # a.yml
    includes:
      - common
    environments:
      dev:
      prod:

    # b.yml
    includes:
      - common
    environments:
      dev:
      test:
      prod:

    # includes/common.yml
    environments:
      dev:
      test:
      prod:


### `helpers:`

Custom helper functions may be used by templates. Since we're injecting code into our runtime, the
configuration file must explicitly declare any helpers here.


### `core`:

Configuration that changes behavior of the 'stk' application rather configuration/template
deployment.

## Usage

TODO

<p align="right">(<a href="#top">back to top</a>)</p>

This section provides a quick overview of concepts
### Terminology

* **Environment**. What “level” are deploying a stack. E.g. development, test, stage, production, etc.
* **Template**. A YAML CloudFormation template (with Jinja2 templates, so yes — we're templating templates).
* **Archetype**. A common architectural building block that we deploy into each tier. I.e. same business function, but in dev, test, stage etc.
* **Configuration File**. A YAML file that defines what CloudFormation stacks are to be deployed. There are two flavours
  of configuration file:
  * Top-level configuration files. These define what *environments* a given stack can be deployed - i.e. 1:1 mapping of top-level config files to *archetype*.
  * Include files. These are YAML files, mostly same structure as top-level configuration, but exist only to reduce copy
    & paste between top-level configuration files. These are stored in an `includes/` directory.
* **Stack**. A CloudFormation stack. For our purpose, it is an instance of an Archetype - i.e. template + configuration file + tier.

Durning development, we typically work with two git repositories:

* Configuration files (`$CONFIG_PATH`)
* Templates (`$TEMPLATES_PATH`)

Often the template and configuration filenames are the same — so I typically use `.yml` extension for config files, and `.yaml` for templates. YMMV.

## Roadmap

See the [open issues](https://github.com/jwoffindin/stk/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>

## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>


## Contact

John Woffindin - [@john_woffindin](https://twitter.com/john_woffindin) - j.woffindin@gmail.com

Project Link: [https://github.com/jwoffindin/stk](https://github.com/jwoffindin/stk)

<p align="right">(<a href="#top">back to top</a>)</p>

## Acknowledgments

TODO

<p align="right">(<a href="#top">back to top</a>)</p>


[contributors-shield]: https://img.shields.io/github/contributors/jwoffindin/stk.svg?style=for-the-badge
[contributors-url]: https://github.com/jwoffindin/stk/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/jwoffindin/stk.svg?style=for-the-badge
[forks-url]: https://github.com/jwoffindin/stk/network/members
[stars-shield]: https://img.shields.io/github/stars/jwoffindin/stk.svg?style=for-the-badge
[stars-url]: https://github.com/jwoffindin/stk/stargazers
[issues-shield]: https://img.shields.io/github/issues/jwoffindin/stk.svg?style=for-the-badge
[issues-url]: https://github.com/jwoffindin/stk/issues
[license-shield]: https://img.shields.io/github/license/jwoffindin/stk.svg?style=for-the-badge
[license-url]: https://github.com/jwoffindin/stk/blob/master/LICENSE.txt
[product-screenshot]: images/screenshot.png
