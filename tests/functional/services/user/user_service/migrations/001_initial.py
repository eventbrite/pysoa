from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    # noinspection SqlNoDataSourceInspection
    operations = [
        migrations.RunSQL("""
CREATE TABLE users (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email` VARCHAR(512) NOT NULL,
    `password` VARCHAR(128) NOT NULL,
    PRIMARY KEY `users_pk` (`id`),
    UNIQUE KEY `users_email` (`email`)
) ENGINE InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
"""),
    ]
