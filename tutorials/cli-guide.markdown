---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: tutorial
title: CLI Guide
permalink: cli-guide
---
<h4 id="usage">Usage</h4>
<pre><code>orbit [OPTIONS] COMMAND [ARGS]…
</code></pre>
<h4 id="options">Options</h4>
<pre><code>--help  Show this message and exit.
</code></pre>
<h4 id="commands">Commands</h4>
<pre><code>build    Build images,profiles,etc in your Orbit Workbench.
delete   Delete images,profiles,etc in your Orbit Workbench.
deploy   Deploy foundation,env,teams in your Orbit Workbench.
destroy  Destroy foundation,env,etc in your Orbit Workbench.
init     Creates a Orbit Workbench manifest model file (yaml) where all…
list     List images,profiles,etc in your Orbit Workbench.
run      Execute containers in the Orbit environment
</code></pre>
<h2 id="commands_1">Commands</h2>
<h1 id="build">build</h1>
<p>Build images,profiles,etc in your Orbit Workbench.</p>
<p><strong>Usage:</strong></p>
<pre><code>build [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="image">image</h2>
<p>Build and Deploy a new Docker image into ECR.</p>
<p><strong>Usage:</strong></p>
<pre><code>build image [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -d, --dir TEXT        Dockerfile directory.  [required]
  -n, --name TEXT       Image name.  [required]
  -s, --script TEXT     Build script to run before the image build.
  -t, --team TEXT       One or more Teams to deploy the image to (can de
                        declared multiple times).

  --build-arg TEXT      One or more --build-arg parameters to pass to the
                        Docker build command.

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<h2 id="profile">profile</h2>
<p>Build and Deploy a new Docker image into ECR.</p>
<p><strong>Usage:</strong></p>
<pre><code>build profile [OPTIONS] PROFILE
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -t, --team TEXT       Orbit Team.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<hr />
<h1 id="delete">delete</h1>
<p>Delete images,profiles,etc in your Orbit Workbench.</p>
<p><strong>Usage:</strong></p>
<pre><code>delete [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="image_1">image</h2>
<p>Destroy a Docker image from ECR.</p>
<p><strong>Usage:</strong></p>
<pre><code>delete image [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -n, --name TEXT       Image name.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<h2 id="profile_1">profile</h2>
<p>Build and Deploy a new Docker image into ECR.</p>
<p><strong>Usage:</strong></p>
<pre><code>delete profile [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -t, --team TEXT       Orbit Team.  [required]
  -p, --profile TEXT    Profile name to delete  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<hr />
<h1 id="deploy">deploy</h1>
<p>Deploy foundation,env,teams in your Orbit Workbench.</p>
<p><strong>Usage:</strong></p>
<pre><code>deploy [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="env">env</h2>
<p>Deploy a Orbit Workbench environment based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>deploy env [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -f, --filename TEXT             The target Orbit Workbench manifest file
                                  (yaml).

  -u, --username TEXT             Dockerhub username (Required only for the
                                  first deploy).

  -p, --password TEXT             Dockerhub password (Required only for the
                                  first deploy).

  --skip-images / --no-skip-images
                                  Skip Docker images updates (Usually for
                                  development purpose).  [default: False]

  --debug / --no-debug            Enable detailed logging.  [default: False]
  --help                          Show this message and exit.
</code></pre>
<h2 id="foundation">foundation</h2>
<p>Deploy a Orbit Workbench foundation based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>deploy foundation [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -f, --filename TEXT             The target Orbit Workbench manifest file
                                  (yaml).

  -n, --name TEXT                 The Name of the Orbit Foundation deployment
  -u, --username TEXT             Dockerhub username (Required only for the
                                  first deploy).

  -p, --password TEXT             Dockerhub password (Required only for the
                                  first deploy).

  --codeartifact-domain TEXT      CodeArtifact Domain to pull packages from.
  --codeartifact-repository TEXT  CodeArtifact Repository to pull packages
                                  from.

  --internet-accessiblity / --no-internet-accessiblity
                                  Configure for deployment to Private
                                  (internet accessiblity) or Isolated (no
                                  internet accessibility) subnets.  [default:
                                  True]

  --debug / --no-debug            Enable detailed logging.  [default: False]
  --help                          Show this message and exit.
</code></pre>
<h2 id="teams">teams</h2>
<p>Deploy a Orbit Workbench environment based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>deploy teams [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -f, --filename TEXT   The target Orbit Workbench manifest file (yaml).
  -u, --username TEXT   Dockerhub username (Required only for the first
                        deploy).

  -p, --password TEXT   Dockerhub password (Required only for the first
                        deploy).

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<hr />
<h1 id="destroy">destroy</h1>
<p>Destroy foundation,env,etc in your Orbit Workbench.</p>
<p><strong>Usage:</strong></p>
<pre><code>destroy [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="env_1">env</h2>
<p>Destroy a Orbit Workbench environment based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>destroy env [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Destroy Orbit Environment.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<h2 id="foundation_1">foundation</h2>
<p>Destroy a Orbit Workbench environment based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>destroy foundation [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -n, --name TEXT       Destroy Orbit Foundation.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<h2 id="teams_1">teams</h2>
<p>Destroy a Orbit Workbench environment based on a manisfest file (yaml).</p>
<p><strong>Usage:</strong></p>
<pre><code>destroy teams [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Destroy Orbit Teams.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<hr />
<h1 id="init">init</h1>
<p>Creates a Orbit Workbench manifest model file (yaml) where all your deployment settings will rest.</p>
<p><strong>Usage:</strong></p>
<pre><code>init [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -n, --name TEXT                 The name of the Orbit Workbench enviroment.
                                  MUST be unique per AWS account.  [default:
                                  my-env]

  -r, --region TEXT               AWS Region name (e.g. us-east-1). If None,
                                  it will be infered.

  --foundation / --no-foundation  Create Orbit foundation default manifest.
                                  [default: True]

  --debug / --no-debug            Enable detailed logging.  [default: False]
  --help                          Show this message and exit.
</code></pre>
<hr />
<h1 id="list">list</h1>
<p>List images,profiles,etc in your Orbit Workbench.</p>
<p><strong>Usage:</strong></p>
<pre><code>list [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="env_2">env</h2>
<p>List all Docker images available into the target environment.</p>
<p><strong>Usage:</strong></p>
<pre><code>list env [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --debug / --no-debug            Enable detailed logging.  [default: False]
  --variable [all|landing-page|teams|toolkitbucket]
                                  [default: all]
  --help                          Show this message and exit.
</code></pre>
<h2 id="image_2">image</h2>
<p>List all Docker images available into the target environment.</p>
<p><strong>Usage:</strong></p>
<pre><code>list image [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -r, --region TEXT     AWS Region name (e.g. us-east-1). If None, it will be
                        infered.

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<h2 id="profile_2">profile</h2>
<p>Build and Deploy a new Docker image into ECR.</p>
<p><strong>Usage:</strong></p>
<pre><code>list profile [OPTIONS]
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT        Orbit Environment.  [required]
  -t, --team TEXT       Orbit Team.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
</code></pre>
<hr />
<h1 id="run">run</h1>
<p>Execute containers in the Orbit environment</p>
<p><strong>Usage:</strong></p>
<pre><code>run [OPTIONS] COMMAND [ARGS]...
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  --help  Show this message and exit.
</code></pre>
<h2 id="notebook">notebook</h2>
<p>Run notebook in a container</p>
<p><strong>Usage:</strong></p>
<pre><code>run notebook [OPTIONS] INPUT
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT                Orbit Environment to execute container in.
                                [required]

  -t, --team TEXT               Orbit Team Space to execute container in.
                                [required]

  -u, --user TEXT               Jupyter user to execute container as.
                                [default: jovyan]

  --wait / --no-wait            Wait for execution to complete.  [default:
                                False]

  --delay INTEGER               If --wait, this is the number of seconds to
                                sleep between container state checks.

  --max-attempts INTEGER        If --wait, this is the number of times to
                                check container state before failing.

  --tail-logs / --no-tail-logs  If --wait, print a tail of container logs
                                after execution completes.  [default: False]

  --debug / --no-debug          Enable detailed logging.  [default: False]
  --help                        Show this message and exit.
</code></pre>
<h2 id="python">python</h2>
<p>Run python script in a container</p>
<p><strong>Usage:</strong></p>
<pre><code>run python [OPTIONS] INPUT
</code></pre>
<p><strong>Options:</strong></p>
<pre><code>  -e, --env TEXT                Orbit Environment to execute container in.
                                [required]

  -t, --team TEXT               Orbit Team Space to execute container in.
                                [required]

  -u, --user TEXT               Jupyter user to execute container as.
                                [default: jovyan]

  --wait / --no-wait            Wait for execution to complete.  [default:
                                False]

  --delay INTEGER               If --wait, this is the number of seconds to
                                sleep between container state checks.

  --max-attempts INTEGER        If --wait, this is the number of times to
                                check container state before failing.

  --tail-logs / --no-tail-logs  If --wait, print a tail of container logs
                                after execution completes.  [default: False]

  --debug / --no-debug          Enable detailed logging.  [default: False]
  --help                        Show this message and exit.
</code></pre>
