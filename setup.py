from setuptools import Extension, setup

setup(ext_modules=[Extension("linux", sources=["linux.c"])])
