# eGun Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/IPv777/ha-egun)](https://github.com/IPv777/ha-egun/releases)

Intégration Home Assistant personnalisée permettant de surveiller en continu les enchères et ventes immédiates de carabines sur la plateforme allemande **eGun.de**.

---

## 🎯 Fonctionnalités Clés

* **Scraping Haute Précision** : Exploitation directe du timestamp d'échéance UNIX (`data-ends`) fourni par eGun pour une précision à la seconde près.
* **Veille Spécifique Calibres** :
  * Préset **.30-06** (`cat=72`, `query="30 06"`, livraison France `shipto=8`)
  * Préset **.308 Win** (`cat=72`, `query="308"`, livraison France `shipto=8`)
  * Mode personnalisé pour toute catégorie ou mots-clés
* **Filtrage Intelligent des Accessoires** : Distingue automatiquement les carabines complètes des pièces détachées (chargeurs seuls, crosses, percuteurs, munitions factices).
* **Détection du Mécanisme & Équipement** :
  * Culasse linéaire (*Geradezug*, Merkel RX Helix, Browning Maral, Beretta BRX1, Blaser R93/R8, Heym SR30, Savage Impulse, Steel Action) vs culasse à verrou (*Repetierer*).
  * Optiques et points rouges montés (Zeiss, Swarovski, Schmidt & Bender, Kahles, Meopta, Steiner, Kaps, Leupold, Aimpoint...).
  * Canons filetés et modérateurs de son (*Gewinde*, *Schalldämpfer*).
* **Mode Turbo Sprint Dynamique** : Polling accéléré à 3 minutes dès qu'une enchère se termine dans moins de 2 heures.
* **Alertes Push d'Urgence (ThinkPhone)** :
  * Notification urgente à **1h de la fin d'enchère** si le prix reste sous le budget maximal.
  * Notification immédiate lors de la parution d'une nouvelle offre.
  * Boutons d'action : *"Voir sur eGun 🎯"* et *"Ignorer 🔕"*.
* **Actions et Services** :
  * `egun.refresh` : Scraping immédiat à la demande.
  * `egun.set_budget` : Ajustement dynamique du budget maximal en direct.
  * `egun.mute_item` / `egun.unmute_item` : Masquage d'une offre.
  * `egun.reset_cache` : Remise à zéro de l'historique des annonces vues.
* **Lovelace Ready** : Attributs compacts sous la limite des 16 Ko pour une parfaite intégration avec `custom:flex-table-card` et `type: "sections"`.

---

## 📦 Installation via HACS

1. Ouvrez **HACS** > **Intégrations**.
2. Cliquez sur les 3 points en haut à droite > **Dépôts personnalisés**.
3. Ajoutez l'URL du dépôt : `https://github.com/IPv777/ha-egun` avec la catégorie **Intégration**.
4. Cliquez sur **Télécharger**, puis redémarrez Home Assistant.
5. Allez dans **Paramètres** > **Appareils et services** > **Ajouter une intégration** > recherchez **eGun**.

---

## ⚙️ Configuration

L'assistant graphique propose directement de choisir le calibre à surveiller :
* **Carabines 30-06**
* **Carabines 308**
* **Recherche personnalisée**

Options configurables :
* Budget maximal en € (par défaut 600 €)
* Intervalle de scrutation normale (par défaut 15 minutes)
* Service de notification (par défaut `notify.mobile_app_thinkphone_by_motorola`)
* Exclusion des accessoires stricts

---

## 📜 Licence
Distribué sous licence MIT.
