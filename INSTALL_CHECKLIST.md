# Installation checklist

Ez az ellenőrzőlista egy friss gép előkészítését írja le a Python szkriptek és a Unity projekt futtatásához.

## 1. A repository klónozása

- [ ] Telepítsd a [Git](https://git-scm.com/downloads) legfrissebb stabil verzióját.
- [ ] Ellenőrizd a telepítést:

  ```bash
  git --version
  ```

- [ ] Klónozd a repositoryt, majd lépj be a projekt könyvtárába:

  ```bash
  git clone <REPOSITORY_URL>
  cd <REPOSITORY_KONYVTARA>
  ```

## 2. Unity telepítése

- [ ] Töltsd le és telepítsd a [Unity Hubot](https://unity.com/download).
- [ ] Jelentkezz be a Unity-fiókodba, és szükség esetén aktiválj licencet.
- [ ] A Unity Hub **Installs** nézetében válaszd az **Install Editor** lehetőséget.
- [ ] Telepítsd pontosan a **Unity 6000.3.20f1 LTS** verziót.
- [ ] Válaszd ki a projekthez szükséges build modulokat (például Windows, macOS, Linux, Android vagy WebGL támogatás).
- [ ] A Unity Hub **Projects** nézetében válaszd az **Add/Open** lehetőséget, majd nyisd meg a repository Unity projektet tartalmazó könyvtárát.
- [ ] Ellenőrizd, hogy a projekt hiba nélkül megnyílik, és a Unity Console nem jelez fordítási hibát.

## 3. Python 3.9 telepítése

- [ ] Telepítsd a **Python 3.9** legfrissebb elérhető javítóverzióját a [python.org](https://www.python.org/downloads/) oldalról vagy egy rendszerhez illő verziókezelővel.
- [ ] Windows alatt a telepítőben jelöld be az **Add Python to PATH** lehetőséget.
- [ ] Ellenőrizd, hogy a megfelelő verzió érhető el:

  ```bash
  python3.9 --version
  ```

  Windows alatt szükség esetén:

  ```powershell
  py -3.9 --version
  ```

## 4. Virtuális környezet létrehozása

- [ ] A repository gyökérkönyvtárában hozd létre a virtuális környezetet.

  macOS vagy Linux:

  ```bash
  python3.9 -m venv .venv
  source .venv/bin/activate
  ```

  Windows PowerShell:

  ```powershell
  py -3.9 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

- [ ] Frissítsd a csomagtelepítőt:

  ```bash
  python -m pip install --upgrade pip
  ```

- [ ] Telepítsd a rögzített Python-függőségeket (lock-fájl):

  ```bash
  python -m pip install -r requirements-ci.txt
  ```

## 5. A telepítés ellenőrzése

- [ ] macOS vagy Linux alatt tedd futtathatóvá az ellenőrző scriptet:

  ```bash
  chmod +x scripts/doctor
  ```

- [ ] A repository gyökérkönyvtárából, aktív virtuális környezetben futtasd:

  ```bash
  ./scripts/doctor
  ```

- [ ] Windows alatt, ha a script közvetlenül nem futtatható, indítsd a fájl típusának megfelelő shellből (például Git Bash vagy WSL), vagy kövesd a scriptben megadott Windows-specifikus utasítást.
- [ ] Ellenőrizd, hogy a `doctor` minden szükséges összetevőnél sikeres eredményt jelez: Git, Python 3.9, virtuális környezet, Python-függőségek és Unity 6000.3.20f1 LTS.
- [ ] Ha valamelyik ellenőrzés hibát jelez, javítsd a megadott problémát, majd futtasd újra a scriptet.

## 6. Végső próba

- [ ] Futtass egy Python szkriptet az aktív virtuális környezetből.
- [ ] Nyisd meg a Unity projektet a Unity Hubon keresztül a **6000.3.20f1 LTS** Editorral.
- [ ] Indítsd el a projekt fő jelenetét Play módban, és ellenőrizd, hogy nincs hiba a Console ablakban.
