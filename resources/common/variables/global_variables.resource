*** Variables ***
# Configuración por defecto de entorno (puede sobreescribirse con: --variable ENV:prod)
${ENV}                           dev
${CONFIG}                        ${None}
${LOCATORS}                      ${None}

# Parámetros inyectables de ejecución; no persistir enlaces de invitación, credenciales ni cookies.
${AMAZON_WISHLIST_URL}           ${EMPTY}
${AMAZON_CHROME_USER_DATA_DIR}   ${EMPTY}
${AMAZON_CHROME_PROFILE_NAME}    Default
${AMAZON_CHROME_DEBUG_PORT}      ${EMPTY}
${AMAZON_CHROME_BINARY_PATH}     ${EMPTY}
${HEADLESS}                      ${False}

# Rutas estándar del proyecto
${INPUT_DIR}                     ${CURDIR}${/}..${/}..${/}data${/}input
${DATA_OUTPUT_DIR}               ${CURDIR}${/}..${/}..${/}data${/}output
${TEMP_DIR}                      ${CURDIR}${/}..${/}..${/}data${/}temp
${RESULTS_DIR}                   ${CURDIR}${/}..${/}..${/}results

# Métricas del ciclo de actualización de wishlist
${TOTAL_ITEMS}                   ${0}
${SUCCESSFUL_ITEMS}              ${0}
${PRICE_DECREASES}               ${0}
${PRICE_INCREASES}               ${0}
${UNAVAILABLE_ITEMS}             ${0}
${BUSINESS_EXCEPTIONS}           ${0}
${SYSTEM_EXCEPTIONS}             ${0}
