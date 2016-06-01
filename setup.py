from setuptools import setup, find_packages
import os.path

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()

version = '1.5'

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
      ],
      keywords='',
      author='Tim Hatch',
      author_email='tim@timhatch.com',
      url='https://github.com/thatch/regexlint',
      license='Apache',
      packages=find_packages('.'),
      install_requires=['Pygments'],
      entry_points={
        'console_scripts': [
            'regexlint=regexlint.cmdline:main',
        ],
      },
      test_suite='nose.collector',
      tests_require=['nose'],
)
