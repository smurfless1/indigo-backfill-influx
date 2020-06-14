from invoke import task


@task
def proto(c):
    c.run("protoc -I . --python_betterproto_out=. indigo.proto")