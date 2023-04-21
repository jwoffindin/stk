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

<h3 align="center">CloudFormation doesn't have to suck 😉</h3>

  <p align="center">
    STK - improved infrastructure management with CloudFormation.</p>
</div>

## About The Project

STK provides an opinionated framework for better management of your AWS infrastructure with CloudFormation.

Some benefits of using `stk` for CloudFormation management.

* Encourages **composition of infrastructure through re-use of small, modular, sharable CloudFormation templates** over monolithic, complex templates. Think "lego" for infrastructure. Put together these Lego blocks in any number of combinations to deliver the infrastructure your business requires.
* **Decouple CloudFormation templates (code) from configuration**. It's as good for your infrastructure as it is for your applications. Templates are stored in external Git repositories separate from configuration. Compose from a variety of private and open source template repositories.
* **Reduce change risk through improved visibility** and simpler templates. Use of Jinja2 for templates and use of explicit configuration (directly interpolated variables) over implicit configuration (AWS parameters) means you can see exactly what is going to change.

### Local installation (Python/Pip)

STK is written in Python. Install it from GitHub using Python pip, or use the docker image for your CI/CD pipelines:

> **Note**:
> Requires **python 3.10+**

Install STK via pip

    pip install cfn-stk

Alternatively

    python3 -m pip install cfn-stk

Docker images are available from <https://hub.docker.com/repository/docker/johnwo/stk>.

<p align="right">(<a href="#top">back to top</a>)</p>


## Getting started

> **Note**: Quick start: The `cfn init` command will help you get started by creating a skeleton "configuration project":

```bash
cfn config init my-project --repo git@github.com:jwoffindin/stk-templates.git
cd my-project
```

> **Note**: `init` will configure an S3 bucket to store CloudFormation templates. You must select an AWS profile with currently valid credentials, otherwise the command will fail trying to list available buckets.

The GitHub project <https://github.com/jwoffindin/stk-templates> has several starter
templates that you can use. For example, to use the `vpc` template to deploy a VPC into
your AWS account:

```bash
cfn config add vpc
```

this will create a file `vpc.yml` with starter configuration. You can deploy to AWS with:

```bash
cfn deploy vpc dev
```


## Terminology

* **Environment**. What “level” are deploying a stack. E.g. development, test, stage, production, etc.
* **Template**. A YAML CloudFormation template (with Jinja2 templates, so yes — we're templating templates).
* **Archetype**. A common architectural building block that we deploy into each tier. I.e. same business function, but in dev, test, stage etc.
* **Configuration File**. A YAML file that defines what CloudFormation stacks are to be deployed. There are two flavours
  of configuration file:
  * Top-level configuration files. These define what *environments* a given stack can be deployed - i.e. 1:1 mapping of top-level config files to *archetype*.
  * Include files. These are YAML files, mostly same structure as top-level configuration, but exist only to reduce copy
    & paste between top-level configuration files. These are stored in an `includes/` directory.
* **Stack**. A CloudFormation stack. For our purpose, it is an instance of an Archetype - i.e. template + configuration file + tier.

## Commands

A full list of commands are available by running `stk help`

The most common commands that you would use are listed below. They are invoked as `cfn <command> <config-file> <environment>`

* `show-config` - show configuration that will be passed to a template.
* `show-template` - displays resulting CloudFormation template by applying configuration to template.
* `diff` - show the proposed changes between locally rendered CloudFormation Template and the currently deployed template. Displays a text diff between current and proposed templates
* `validate` - validates that a template is ready to be deployed. Performs validation of configuration and template, as well as submitting the template to AWS CloudFormation APIs for validation.
* `create` — deploys a new stack. Will fail if the stack exists already.
* `update` - update an existing stack
* `deploy` - an alias for create/update commands ("upsert"). Will update if the stack exists already, otherwise it will create a new stack.

### Configuration file

A configuration file is simply a YAML file that declares:

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

This configuration file will allow us to deploy `dev`, `test` and `prod` instances of a CloudFormation stack from the template
`foo.yaml` into the `ap-southeast-2 `region.

Do deploy this stack `foo-dev` into `ap-southeast-2` using default credentials.

```sh
stk deploy foo dev
```

Create and apply a change set to the `foo-test` stack in ap-southeast-2 region.

```sh
stk update foo test
```

### CloudFormation Templates

The CloudFormation templates are YAML (JSON may work, I've not tried it). They are processed through `Jinja2` (much as is done with Ansible). Any variables declared in `vars:` section of a config file are available within the template.

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

To avoid confusion between YAML comments and Jinja2 block level operations, `stk` uses a `##` for Jinja2. For example, if we want to allow `greeting` to be optional, the template would look like:

```yaml
# $TEMPLATE_PATH/foo.yaml

## if greeting is defined
Description: |
  I'd like to say {{ greeting }}, to you all
## endif

```

## Configuration

Configuration is generally stored in a different git repository from the actual templates. In the following examples, `$CONFIG_DIR` is used to represent where configuration files are stored, and `$TEMPLATE_DIR` where the CloudFormation templates live.
### Structure

The top-level keys that can be declared in a configuration file are:

* `includes` - include additional configuration files
* `template` - where to find the CloudFormation template
* `params` - AWS CloudFormation parameter definitions
* `vars` - Configuration variables (Jinja2)
* `refs` - Retrieve information from other CloudFormation stacks
* `tags` - Default tags to apply to the CloudFormation stack
* `aws` - Defines how to connect to AWS, what region to deploy etc.
* `environments` - Environment-specific overrides.
* `helpers` - Supports defining Python helpers in templates for more complex logic.
* `core` - Adjust some core `stk` settings.

These are explained in more detail below.

#### `includes`

Allows composition and sharing of common configuration to reduce unnecessary duplication.

It is a list of YAML files loaded from `includes/` directory. The `.yml`/`.yaml` extension is optional.

Includes are listed in highest-to-lowest precedence. Settings defined in any include file have a lower precedence than the current file.


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

Two common use cases for include files are:

1. Environment specific configuration - e.g. AWS account details
1. Where multiple config files use the sample template with common settings.


### `template`

Defines where to stk can find the CloudFormation template. Supports local files, local git repositories and remote git repositories.

Templates are typically stored separately to the configuration project so they can be shared between teams.
Well-written templates are re-usable components that can be composed to build your final architecture (again, think Lego blocks).

The sources for templates are:
#### Plain filesystem (not git)

If `version` is not set, then the templates are assumed to come from local filesystem - useful
when developing templates or where templates don't need to be reused. In this case, set `root` to path.

E.g.

    environments:
      dev:
        template:
          version:
          root: ./templates

During development, you can use an environment variable to define the template location:

    environments:
      dev:
        template:
          version:
          root: {{ environ['TEMPLATE_PATH'] }}

#### Local Git Repository

Similar to above, but uses current commit `HEAD` in local filesystem:

    environments:
      dev:
        template:
          version: HEAD
          repo: {{ environ['TEMPLATE_PATH'] }}

#### Remote Git Repository

Remote repositories are also supported. For example, the following will use `main` branch of a github repository:

    template:
      version: main
      repo: git@github.com:jwoffindin/stk-templates.git

Note: `stk` creates a `.template-cache` directory when run - it's highly recommended that you add this to your `.gitignore` file.



### `params`

AWS Parameters that are passed into a stack. Minimize if possible, use `vars` instead.

Good use cases for `Params` include:
 * passing secrets
 ...
 * (that's about it?)

Example:

```
params:
  MySubnetId: sub-0123456789
```

Params values are usually environment-specific. They can be overridden on a per environment basis, as illustrated in the following example:

```
params:
  MySubnetId: sub-0123456789

environments:
  dev:
  test:
  stage:
    params:
      MySubnetId: sub-abcdef
```

In this case deployments of `dev` and `test` will have `MySubnetId` of `sub-0123456789` (the default), and `stage` will be `sub-abcdef`

Parameters can be automatically JSON-encoded (for non-string values), by setting
`core.encode_params` to `true`. This will simplify passing JSON-style data as parameters.

For example:

```
core:
  encode_params: true

params:
  someComplexValue: { "key": "value" }
```


### `vars`

Jinja2 variables/values primarily used to pass configuration to to the CloudFormation Template.

`vars are the preferred way to manage configuration (as opposed to `params`) - e.g. use template conditions rather than 'native' AWS Template Conditions - they are unwieldy and can make changes hard to reason about.

As shown in examples above, vars are used in templates for interpolation, conditions etc. For example:

```yaml
# config file
vars:
  queue_name: "MyQueue"
```

```yaml
# template
Resources:
  MyQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: "{{ queue_name }}"
```

Like `params`, `vars` can have environment-specific overrides. Following the previous example, the following config file would allow deploying queues of different names to `dev` and `test`:

```yaml
# config file
environments:
  dev:
    vars:
      queue_name: "MyDevQueue"
  test:
    vars:
      queue_name: "MyTestQueue"
```

Configuration _values_ are processed though Jinja2 (although the file itself is *not* a Jinja template). Many
patterns are stolen from Ansible, so some concepts may be familiar if you've used Ansible.

For example:

```yaml
# $CONFIG_PATH/foo.yml
aws:
  cfn_bucket: my-bucket-for-{{ environment }}-cloudformation-deployments
```

Declares a different bucket per tier.

Similarly:

```yaml
vars:
   hello: "hello, {{ who | default('world') }}!"

environments:
  dev:
  test:
    vars:
      who: me
```

In this example, deploying to dev, `hello` will have the value `hello, world!`, but the value in test will be `hello, me!`.

### `refs` - Referencing other stack outputs

Use `refs:` to retrieve Outputs from other stacks and feeding them as inputs into your stack.

Refs is a map/dict of names and options. Refs are available to templates and configuration.

For example, if you have a VPC stack deployed from which you need to retrieve subnet IDs, which are exposed as `Subnets` output, you can do something like:

```yaml
refs:
  vpc:

vars:
  subnets: "{{ refs.vpc.Subnets }}"
```

will query the `Subnets` output from the vpc stack and pass in a list of subnets to the template as a var.

#### Optional references

Some stacks may be optional. A referenced output will return nil/blank value
if the stack doesn't exist.

For example:

```yaml
refs:
  an_optional_stack:
    optional: true

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

### `tags`

Tags that are applied to the stack (and thus resources within the stack)

### `aws`

Information about the AWS account being deployed into. At a minimum needs region and name of the s3 bucket for uploading deployment artifacts.


### `environments`

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

For example:

```
...
environments:
  dev:
    tags:
      Owner: "mary.jane@acme.com"
  test:
    tags:
      Owner: "bob.smith@acme.com"
tags:
  Environment: "{{ environment }}"
```

#### Valid deployment environments

Within an top-level config file, `environments` defines the allowable deployment
targets. Environments defined in include files are not used for this purpose.

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


### `helpers`

Custom helper functions may be used by templates. Since we're injecting code into our runtime, the configuration file must explicitly declare any helpers here.

### `core`

Configuration that changes behavior of the 'stk' application rather configuration/template deployment.

## Configuration Hierarchy

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



<p align="right">(<a href="#top">back to top</a>)</p>

## Environment Variables

| Name | Purpose |
| ---- | ------- |
| `CONFIG_PATH` | Default path to configuration files, override with `--config-path` |
| `TEMPLATE_PATH` | Default path to templates, usually overridden by config (`template.*`) or `--template-path` cli argument |
| `TEMPLATE_CACHE` | Override the path to template cache (local copy of template project for git projects only)  |

## Logging

By default internal logs are sent to syslog with WARN.

The following environment variables can be used to change this behaviour

| Environment variable | Purpose | Example |
| --- | --- | --- |
| `CFN_LOG_LEVEL` | Change log level | `DEBUG`, `INFO`, `ERROR` |
| `LOG_LEVEL` | Fallback log level. Also used by boto, so will change boto logging too | `INFO`, `WARN` |
| `LOG_FILE` | Direct logging to this file rather than syslog | `./cfn.log` |

## Exit codes

| Exit code | Reason |
| --- | --- |
| -1  | General failure |
| -2  | Could not generate change set |
| -9  | No change to apply |


## Roadmap

See the [open issues](https://github.com/jwoffindin/stk/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#top">back to top</a>)</p>

## Alternatives

`stk` is rather opinionated about managing CloudFormation. If this approach doesn't work for you, check out these alternatives:

* [Sceptre](https://github.com/Sceptre/sceptre) - a more mature project that takes a similar, less opinionated, approach to the problem. Supports stack sets. Only supports local (to the filesystem) templates.
   > Sceptre is a tool to drive AWS CloudFormation. It automates the mundane, repetitive and error-prone tasks, enabling you to concentrate on building better infrastructure.


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
