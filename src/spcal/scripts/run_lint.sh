# black
black ./src/spcal

# autoflake
autoflake --in-place --remove-all-unused-imports ./src/spcal/*.py

# isort
isort ./src/spcal
