from setuptools import setup, find_packages

setup(
    name='omniture',
    description='A wrapper for the Adobe Omniture and SiteCatalyst web analytics API.',
    long_description=
    """
    python-omniture is a wrapper around the Adobe Omniture web analytics API.

    It is not meant to be comprehensive. Instead, it provides a high-level interface to certain
    common kinds of queries, and allows you to do construct other queries closer to the metal.
    """,
    author='Stijn Debrouwere',
    author_email='stijn@stdout.be',
    url='http://stdbrouw.github.com/python-omniture/',
    download_url='http://www.github.com/stdbrouw/python-omniture/tarball/master',
    version='0.3.1',
    license='MIT',
    packages=find_packages(),
    keywords='data analytics api wrapper adobe',
    install_requires=[
        'requests',
        'python-dateutil',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Information Analysis',
    ],
)
