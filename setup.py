from setuptools import setup, find_packages
import os.path

with open('README.rst') as f:
    README = f.read()

with open('requirements.txt') as f:
    requires = f.read().strip().splitlines()

version = '1.6'

setup(name='regexlint',
      version=version,
      description='Linter for (Pygments) regular expressions',
      long_description=README,
      classifiers = [
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent', # I hope
        'Topic :: Software Development :: Quality Assurance', # Closest to linting I see
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
      ],
      keywords='',
      author='Tim Hatch',
      author_email='tim@timhatch.com',
      url='https://github.com/thatch/regexlint',
      license='Apache',
      packages=find_packages('.'),
      install_requires=requires,
      entry_points={
        'console_scripts': [
            'regexlint=regexlint.cmdline:main',
        ],
      },
      test_suite='nose.collector',
      tests_require=['nose'],
)
