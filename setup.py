from setuptools import setup, find_packages

setup(
    name="ollama_roocode",
    version="0.1.0",
    description="Ollama + RooCode Document QA System",
    author="Developer",
    packages=find_packages(include=[
        "src*",
        "config*"
    ]),
    package_data={
        "config": ["*.json"],
    },
    python_requires=">=3.10",
    install_requires=[
        "langchain>=0.1.0",
        "chromadb>=0.4.0",
        "google-auth>=2.22.0",
        "google-auth-oauthlib>=1.0.0",
        "google-api-python-client>=2.0.0",
        "PyPDF2>=3.0.0",
        "python-dotenv>=1.0.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
        "tenacity>=8.2.3",
        "tqdm>=4.66.1"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "ollama-roocode=src.main:main"
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ]
)