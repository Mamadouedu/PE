# Swagger UI (vendored)

`swagger-ui.css` et `swagger-ui-bundle.js` viennent de
[`swagger-ui-dist@5`](https://www.npmjs.com/package/swagger-ui-dist),
copiés tels quels (non modifiés) pour servir `/docs` sans dépendre d'un CDN
public — plusieurs réseaux d'entreprise, dont celui qui a motivé la version
sur mesure de ce cahier, bloquent `cdn.jsdelivr.net`.

La version 5 est nécessaire : FastAPI génère un schéma OpenAPI 3.1, que
Swagger UI 4.x ne sait pas afficher (« Unable to render this definition »).

Pour mettre à jour :

```bash
npm install --no-save --prefix /tmp/swagger-fetch swagger-ui-dist@<version>
cp /tmp/swagger-fetch/node_modules/swagger-ui-dist/swagger-ui.css .
cp /tmp/swagger-fetch/node_modules/swagger-ui-dist/swagger-ui-bundle.js .
```
