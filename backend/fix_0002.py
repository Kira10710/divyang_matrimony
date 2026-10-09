import re

with open('alembic/versions/0002_profile_tables.py') as f:
    text = f.read()

# Replace variable usages with inline postgresql.ENUM
replacements = {
    'gender_enum': "postgresql.ENUM('MALE', 'FEMALE', 'OTHER', name='gender_enum', create_type=False)",
    'managed_by_enum': "postgresql.ENUM('SELF', 'PARENT', 'SIBLING', 'GUARDIAN', name='profile_managed_by_enum', create_type=False)",
    'disability_type_enum': "postgresql.ENUM('PHYSICAL', 'VISUAL', 'HEARING', 'INTELLECTUAL', 'MULTIPLE', name='disability_type_enum', create_type=False)",
    'marital_status_enum': "postgresql.ENUM('NEVER_MARRIED', 'DIVORCED', 'WIDOWED', 'SEPARATED', name='marital_status_enum', create_type=False)",
    'verification_status_enum': "postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='verification_status_enum', create_type=False)"
}

for var_name, replacement in replacements.items():
    # Find exact words, mostly used as sa.Column("something", var_name, ...)
    text = re.sub(r'\b' + var_name + r'\b', replacement, text)

with open('alembic/versions/0002_profile_tables.py', 'w') as f:
    f.write(text)

print('Updated 0002_profile_tables.py')
