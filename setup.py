try:
  from setuptools import setup
except ImportError:
  from distutils.core import setup

def requirements():
  """Build the requirements list for this project"""
  requirements_list = []

  with open('requirements.txt') as reqs:
    for install in reqs:
      requirements_list.append(install.strip())

  return requirements_list

setup(
  name='AFX_bot',
  version='1.0.0',
  packages=[''],
  url='',
  license='',
  author='Anfauglir',
  author_email='',
  description='a simple Telegram bot in Python',
  install_requires=requirements()
)
