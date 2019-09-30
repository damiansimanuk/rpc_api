import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="rpc_api",
    version="0.1.dev",
    author="Damian Simanuk",
    author_email="damiansimanuk@gmail.com",
    description="JSON-RPC Annotation and REST Api",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="rpc json tornado starlette pydantic rest api",
    url="https://github.com/damiansimanuk/rpc_api",
    project_urls={
        "Source": "https://github.com/damiansimanuk/rpc_api",
    },
    packages=setuptools.find_packages(exclude=["examples"]),
    python_requires='>=3.6',
    install_requires=['pydantic'],
    extras_require={
        'test': [''],
    },
    tests_require=[''],
    classifiers=[
        'Development Status :: 1 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
    ],
)
