"""Intégration : inscription, mot de passe oublié ou changé, gestion des comptes par l'admin.

S'exécute contre un vrai PostgreSQL si TEST_DATABASE_URL est défini (comme
test_integration_frontend.py) ; sinon les tests sont ignorés. Les e-mails ne sont pas envoyés :
la fonction d'envoi est remplacée par un collecteur qui garde le jeton du lien.
"""
import os
import pathlib

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

BASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="TEST_DATABASE_URL non défini")

MDP = "Mot-de-passe-test-1"
NOUVEAU = "Autre-mot-de-passe-2"
MAILS: list[tuple[int, str, str]] = []   # (user_id, destinataire, jeton)
CREATED_CREDENTIALS: list[tuple[str, str, str]] = []


def _db():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)


@pytest.fixture(scope="module")
def client():
    with psycopg.connect(BASE_URL, autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS predicare_it")
        c.execute("CREATE DATABASE predicare_it")
    from api.security import hash_password

    with _db() as c:
        c.execute((pathlib.Path(__file__).parent / "schema_test.sql").read_text())
        for username, role, ass, pre in [
            ("admin@c.mg", "administrateur", None, None),
            ("gest@c.mg", "gestionnaire", None, None),
            ("assure@c.mg", "assure", "ASS-9CAA1484E0", None),
            ("pro@c.mg", "professionnel_sante", None, "PRE-00214"),
        ]:
            user = c.execute(
                "INSERT INTO utilisateurs "
                "(nom_utilisateur, hash_mot_de_passe, assure_id, prestataire_id) "
                "VALUES (%s,%s,%s,%s) RETURNING utilisateur_id",
                (username, hash_password(MDP), ass, pre),
            ).fetchone()
            c.execute(
                "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) "
                "SELECT %s, role_id FROM roles WHERE nom_role = %s",
                (user["utilisateur_id"], role),
            )
    import api.routers.admin as admin_mod
    import api.routers.auth as auth_mod
    from api.main import app

    def collecte(user_id, to, token):
        MAILS.append((user_id, to, token))
        return True

    def collecte_identifiants(to, identifier, password):
        CREATED_CREDENTIALS.append((to, identifier, password))
        return True

    auth_mod.send_reset_email = collecte
    admin_mod.send_reset_email = collecte
    admin_mod.send_account_credentials = collecte_identifiants
    admin_mod.pseudonymise_account = lambda cin, role: (
        {"assure": "ASS", "professionnel_sante": "PDS",
         "gestionnaire": "GES", "administrateur": "ADM"}[role]
        + "-" + cin[-10:]
    )
    admin_mod.encrypt_account_identity = lambda fields: b"encrypted-test-identity"
    admin_mod.decrypt_account_identity = lambda blob: {"numero_cin": "123456789012"}
    with TestClient(app) as tc:
        yield tc


@pytest.fixture(autouse=True)
def _vider_mails():
    MAILS.clear()
    CREATED_CREDENTIALS.clear()


def _login(client, email, mdp=MDP):
    return client.post("/auth/login", json={"email": email, "password": mdp})


def _auth(client, email, mdp=MDP):
    r = _login(client, email, mdp)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_id(email):
    with _db() as c:
        return c.execute("SELECT utilisateur_id AS i FROM utilisateurs "
                         "WHERE lower(nom_utilisateur)=lower(%s)",
                         (email,)).fetchone()["i"]


def test_comptes_assures_et_prestataires_provisionnes_au_demarrage(client):
    for username, role, identity_key, identity_value in [
        ("ASS-9CAA1484E0", "assure", "assure_id", "ASS-9CAA1484E0"),
        ("PRE-00214", "professionnel_sante", "prestataire_id", "PRE-00214"),
    ]:
        response = _login(client, username, "123456")
        assert response.status_code == 200
        user = response.json()["user"]
        assert user["email"] == username
        assert user["role"] == role
        assert user[identity_key] == identity_value


# ---------- inscription ----------


def _create_admin_user(client, email, role="gestionnaire", cin="123456789012", **link):
    admin = _auth(client, "admin@c.mg")
    payload = _account_payload(email, role, cin, **link)
    response = client.post("/admin/users", headers=admin, json=payload)
    return response


# ---------- création des comptes ----------

def test_inscription_publique_desactivee(client):
    assert client.post("/auth/register", json={}).status_code == 403


def test_admin_cree_un_compte_pseudonymise_et_envoie_les_identifiants(client):
    assert client.get("/admin/users", headers=_auth(client, "gest@c.mg")).status_code == 403

    created = _create_admin_user(
        client,
        "nouveau@c.mg",
        role="assure",
        cin="123456789012",
        assure_id="ASS-1111111111",
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["identifiant"] == "ASS-3456789012"
    assert account["assure_id"] == "ASS-1111111111" and account["is_active"]
    assert len(CREATED_CREDENTIALS) == 1
    to, identifier, password = CREATED_CREDENTIALS[0]
    assert (to, identifier) == ("nouveau@c.mg", account["identifiant"])
    assert len(password) == 16 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)
    assert _login(client, identifier, password).status_code == 200
    assert _login(client, to, password).status_code == 200

    with _db() as c:
        row = c.execute("SELECT assure_id, est_actif FROM utilisateurs "
                        "WHERE nom_utilisateur='triche@c.mg'").fetchone()
    assert row["assure_id"] is None and row["est_actif"] is False


def test_admin_cree_un_compte_sans_email_cin_ni_fiche_assure(client):
    admin = _auth(client, "admin@c.mg")
    response = client.post("/admin/users", headers=admin, json={
        "role": "assure",
        "nom": "Enfant",
        "prenoms": "Test",
        "sexe": "F",
        "date_naissance": "2018-04-12",
        "telephone": "0340000000",
        "email": None,
        "adresse": "Adresse test",
        "ville": "Antananarivo",
        "numero_cin": None,
    })
    assert response.status_code == 201, response.text
    account = response.json()
    assert account["email"] is None
    assert account["assure_id"] is None
    assert account["identifiant"].startswith("ASS-")
    assert account["mot_de_passe_provisoire"]
    assert account["email_envoye"] is False
    assert CREATED_CREDENTIALS == []
    assert _login(client, account["identifiant"], account["mot_de_passe_provisoire"]).status_code == 200
    with _db() as c:
        identity = c.execute(
            "SELECT donnees_chiffrees FROM utilisateurs_identites WHERE utilisateur_id = %s",
            (account["user_id"],),
        ).fetchone()
    assert identity["donnees_chiffrees"] == b"encrypted-test-identity"


# ---------- mot de passe oublié ----------

def test_mot_de_passe_oublie_flux_complet(client):
    inconnu = client.post("/auth/forgot-password", json={"email": "personne@c.mg"})
    connu = client.post("/auth/forgot-password", json={"email": "assure@c.mg"})
    assert inconnu.status_code == connu.status_code == 202
    assert inconnu.json() == connu.json()          # rien ne révèle l'existence du compte
    assert len(MAILS) == 1 and MAILS[0][1] == "assure@c.mg"
    token = MAILS[0][2]

    assert client.post("/auth/reset-password",
                       json={"token": token, "new_password": "court"}).status_code == 422
    ok = client.post("/auth/reset-password", json={"token": token, "new_password": NOUVEAU})
    assert ok.status_code == 200
    assert _login(client, "assure@c.mg", MDP).status_code == 401
    assert _login(client, "assure@c.mg", NOUVEAU).status_code == 200
    # Usage unique
    again = client.post("/auth/reset-password", json={"token": token, "new_password": MDP})
    assert again.status_code == 400
    # Remet le mot de passe d'origine pour les autres tests
    client.post("/auth/forgot-password", json={"email": "assure@c.mg"})
    client.post("/auth/reset-password", json={"token": MAILS[-1][2], "new_password": MDP})


def test_jeton_inconnu_ou_expire_refuse(client):
    faux = client.post("/auth/reset-password",
                       json={"token": "x" * 43, "new_password": NOUVEAU})
    assert faux.status_code == 400
    client.post("/auth/forgot-password", json={"email": "pro@c.mg"})
    token = MAILS[-1][2]
    with _db() as c:
        c.execute("UPDATE reinitialisations_mdp SET expire_le = now() - interval '1 minute' "
                  "WHERE utilisateur_id = %s", (_user_id("pro@c.mg"),))
    expire = client.post("/auth/reset-password", json={"token": token, "new_password": NOUVEAU})
    assert expire.status_code == 400
    assert _login(client, "pro@c.mg", MDP).status_code == 200   # mot de passe inchangé


def test_nouvelle_demande_invalide_l_ancien_lien(client):
    client.post("/auth/forgot-password", json={"email": "gest@c.mg"})
    client.post("/auth/forgot-password", json={"email": "gest@c.mg"})
    ancien, recent = MAILS[-2][2], MAILS[-1][2]
    assert client.post("/auth/reset-password",
                       json={"token": ancien, "new_password": NOUVEAU}).status_code == 400
    assert client.post("/auth/reset-password",
                       json={"token": recent, "new_password": MDP}).status_code == 200


def test_limite_de_demandes_par_heure(client):
    with _db() as c:
        user = c.execute(
            "INSERT INTO utilisateurs (nom_utilisateur, hash_mot_de_passe) "
            "VALUES ('limite@c.mg', 'x') RETURNING utilisateur_id"
        ).fetchone()
        c.execute(
            "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) "
            "SELECT %s, role_id FROM roles WHERE nom_role = 'gestionnaire'",
            (user["utilisateur_id"],),
        )
    for _ in range(5):
        assert client.post("/auth/forgot-password",
                           json={"email": "limite@c.mg"}).status_code == 202
    assert len(MAILS) == 3    # PASSWORD_RESET_MAX_PER_HOUR par défaut


def test_compte_inactif_ne_recoit_aucun_lien(client):
    with _db() as c:
        c.execute(
            "INSERT INTO utilisateurs (email, mot_de_passe_hash, role, actif) "
            "VALUES (%s, %s, 'assure', false)",
            ("attente@c.mg", hash_password(MDP)),
        )
    assert client.post("/auth/forgot-password", json={"email": "attente@c.mg"}).status_code == 202
    assert MAILS == []


# ---------- changement de mot de passe ----------

def test_changement_de_mot_de_passe(client):
    assert _create_admin_user(client, "chg@c.mg", cin="523456789012").status_code == 201
    initial_password = CREATED_CREDENTIALS[-1][2]
    h = _auth(client, "chg@c.mg", initial_password)
    url = "/auth/change-password"
    assert client.post(url, headers=h, json={
        "current_password": "faux", "new_password": NOUVEAU}).status_code == 400
    assert client.post(url, headers=h, json={
        "current_password": initial_password, "new_password": initial_password}).status_code == 400
    assert client.post(url, headers=h, json={
        "current_password": MDP, "new_password": "court"}).status_code == 422
    assert client.post(url, json={
        "current_password": MDP, "new_password": NOUVEAU}).status_code == 401   # sans jeton
    assert client.post(url, headers=h, json={
        "current_password": initial_password, "new_password": NOUVEAU}).status_code == 200
    assert _login(client, "chg@c.mg", initial_password).status_code == 401
    assert _login(client, "chg@c.mg", NOUVEAU).status_code == 200


def test_changement_de_mot_de_passe_verrouille_apres_echecs(client):
    assert _create_admin_user(client, "brute@c.mg", cin="623456789012").status_code == 201
    initial_password = CREATED_CREDENTIALS[-1][2]
    h = _auth(client, "brute@c.mg", initial_password)
    codes = [client.post("/auth/change-password", headers=h, json={
        "current_password": "faux", "new_password": NOUVEAU}).status_code for _ in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429


# ---------- gestion des comptes par l'administrateur ----------

def test_gestion_reservee_a_l_administrateur(client):
    for email in ("gest@c.mg", "assure@c.mg", "pro@c.mg"):
        h = _auth(client, email)
        assert client.get("/admin/users", headers=h).status_code == 403
        assert client.post("/admin/users", headers=h, json=_account_payload(
            "z@c.mg", cin="723456789012",
        )).status_code == 403
    assert client.get("/admin/users").status_code == 401


def test_creation_modification_desactivation(client):
    admin = _auth(client, "admin@c.mg")
    corps = _account_payload(
        "Cree@C.mg", role="professionnel_sante", cin="823456789012",
        prestataire_id="PRE-00999",
    )
    cree = client.post("/admin/users", headers=admin, json=corps)
    assert cree.status_code == 201
    u = cree.json()
    assert u["email"] == "cree@c.mg" and u["prestataire_id"] == "PRE-00999" and u["is_active"]
    assert u["identifiant"].startswith("PDS-")
    assert u["mot_de_passe_provisoire"] and u["email_envoye"]
    assert "hash_mot_de_passe" not in u
    assert client.post("/admin/users", headers=admin, json=corps).status_code == 409

    page = client.get("/admin/users/page?limit=1&offset=0", headers=admin)
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] >= 1

    # La création d'un compte ne nécessite plus de fiche métier existante.
    base = _account_payload("y@c.mg", cin="923456789012")
    assert client.post("/admin/users", headers=admin, json={
        **_account_payload("sans-prestataire@c.mg", cin="323456789012"),
        "role": "professionnel_sante",
    }).status_code == 422
    cree_sans_fiche = client.post("/admin/users", headers=admin, json={
        **base, "role": "assure"})
    assert cree_sans_fiche.status_code == 201
    assert cree_sans_fiche.json()["assure_id"] is None

    # Les rattachements explicitement fournis doivent rester cohérents et valides.
    assert client.post("/admin/users", headers=admin, json={
        **base, "role": "gestionnaire", "assure_id": "ASS-1111111111"}).status_code == 422
    assert client.post("/admin/users", headers=admin, json={
        **base, "role": "professionnel_sante", "prestataire_id": "PRE-77777"}).status_code == 422

    url = f"/admin/users/{u['user_id']}"
    assert client.get(url, headers=admin).json()["email"] == "cree@c.mg"
    assert client.get("/admin/users/999999", headers=admin).status_code == 404

    # Changer de rôle efface le rattachement qui ne s'applique plus
    maj = client.patch(url, headers=admin, json={"role": "gestionnaire"})
    assert maj.status_code == 200
    assert maj.json()["role"] == "gestionnaire" and maj.json()["prestataire_id"] is None
    assert maj.json()["identifiant"].startswith("GES-")

    token = _auth(client, "cree@c.mg")
    assert client.get("/auth/me", headers=token).status_code == 200
    off = client.delete(url, headers=admin)
    assert off.status_code == 200 and off.json()["is_active"] is False
    # Effet immédiat sur un jeton déjà émis
    assert client.get("/auth/me", headers=token).status_code == 401
    assert client.delete(url, headers=admin).status_code == 200      # idempotent

    liste = client.get("/admin/users?statut=actifs&role=gestionnaire&q=CREE", headers=admin)
    assert all(x["email"] != "cree@c.mg" for x in liste.json())


def test_un_admin_ne_peut_pas_se_couper_l_acces(client):
    admin = _auth(client, "admin@c.mg")
    moi = _user_id("admin@c.mg")
    assert client.delete(f"/admin/users/{moi}", headers=admin).status_code == 409
    assert client.patch(f"/admin/users/{moi}", headers=admin,
                        json={"role": "gestionnaire"}).status_code == 409
    assert client.patch(f"/admin/users/{moi}", headers=admin,
                        json={"is_active": False}).status_code == 409
    assert client.get("/auth/me", headers=admin).status_code == 200


def test_deverrouillage_et_lien_de_reinitialisation_par_admin(client):
    admin = _auth(client, "admin@c.mg")
    created = _create_admin_user(client, "lock@c.mg", cin="223456789012")
    assert created.status_code == 201
    initial_password = CREATED_CREDENTIALS[-1][2]
    uid = _user_id("lock@c.mg")
    for _ in range(5):
        assert _login(client, "lock@c.mg", "faux").status_code == 401
    assert _login(client, "lock@c.mg").status_code == 429
    assert client.post(f"/admin/users/{uid}/unlock", headers=admin).status_code == 200
    assert _login(client, "lock@c.mg", initial_password).status_code == 200

    envoi = client.post(f"/admin/users/{uid}/reset-password", headers=admin)
    assert envoi.status_code == 202 and "token" not in envoi.text
    assert len(MAILS) == 1 and MAILS[0][1] == "lock@c.mg"
    assert client.post("/auth/reset-password", json={
        "token": MAILS[0][2], "new_password": NOUVEAU}).status_code == 200
    assert _login(client, "lock@c.mg", NOUVEAU).status_code == 200


def test_operations_sur_les_comptes_sont_auditees_sans_donnees_personnelles(client):
    admin = _auth(client, "admin@c.mg")
    created = _create_admin_user(
        client, "aud@c.mg", role="assure", cin="323456789012",
        assure_id="ASS-1111111111",
    )
    assert created.status_code == 201
    uid = _user_id("aud@c.mg")
    client.post("/auth/forgot-password", json={"email": "aud@c.mg"})
    client.post("/auth/reset-password", json={"token": MAILS[-1][2], "new_password": NOUVEAU})
    h = _auth(client, "aud@c.mg", NOUVEAU)
    client.post("/auth/change-password", headers=h,
                json={"current_password": NOUVEAU, "new_password": MDP})
    client.delete(f"/admin/users/{uid}", headers=admin)
    assert _create_admin_user(
        client, "aud2@c.mg", role="gestionnaire", cin="423456789012",
    ).status_code == 201

    types = {e["event_type"] for e in client.get("/admin/audit-log?limit=500",
                                                 headers=admin).json()}
    assert {"compte_cree", "compte_desactive",
            "mdp_reinitialisation_demandee", "mdp_reinitialise", "mdp_modifie"} <= types
    with _db() as c:
        lignes = c.execute("SELECT entree::text AS e, sortie::text AS s FROM journal_audit "
                           "WHERE type_entite = 'utilisateur'").fetchall()
    texte = " ".join(f"{x['e']} {x['s']}" for x in lignes)
    assert "@" not in texte and MDP not in texte and NOUVEAU not in texte
