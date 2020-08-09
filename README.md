## Import the database structure 

First of all, create a new MYSQL database:

```bash
$ mysql -u root -p
> CREATE DATABASE opis_manager;
> exit;
```

Import the database schema using laravel migrations from [OPIS Manager backend](https://github.com/UNICT-DMI/opis-manager-core)

---

## How to use the scrapers

The tools in the scrapers directory can extract the public OPIS data from the [official site](http://www.rett.unict.it/nucleo/val_did/anno_1617/) of the University of Catania.

These tools require PHP with mbstring, curl, dom, mysql and mysqli. On Ubuntu you can install them using:

```sudo apt-get install php php-mbstring php-curl php-dom php-mysql php-mysqli```

To use them go to scrapers, copy the file **config.php.dist** into **config.php** and configure it for the database mysql.

Well, run the main file **dipartimento.php**, it will extract the opis data and it will import them in the database.
You can run it from the terminal with:

```bash
$ php dipartimento.php
```
