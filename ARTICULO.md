# Una suite de tests de Rails 5× más rápida sin borrar ningún test

Versión escrita de la charla «Cocineros Rubyistas» (Meetup Ruby Sur, Buenos Aires, 20 de octubre de 2026). Los números provienen de mediciones hechas el 15 de octubre de 2026 sobre una aplicación SaaS multi-tenant en Rails 8.1, con Minitest 6 y PostgreSQL 14.

## Resumen

La suite tiene **5.267 tests** (26.734 assertions). En una notebook tardaba **709 segundos**; después de ocho cambios tarda alrededor de **142 segundos**, cinco veces menos. En CI (GitHub Actions, 2 CPUs) pasó de **301 s a 143 s**. No se borró ni se reescribió ningún test: casi todos los cambios son configuración.

| # | Cambio | Dónde |
|---|---|---|
| 1 | Paralelizar los tests | `test/test_helper.rb` |
| 2 | bcrypt al costo mínimo | `test/test_helper.rb` |
| 3 | No renderizar la página de error de desarrollo | `config/environments/test.rb` |
| 4 | Quitar SimpleCov | `Gemfile`, `test/test_helper.rb` |
| 5 | Quitar `minitest-reporters` | `Gemfile`, `test/test_helper.rb` |
| 6 | Quitar Bullet del entorno de test | `config/environments/test.rb` |
| 7 | Log level `warn` | `config/environments/test.rb` |
| 8 | Tablas unlogged y, en CI, Postgres sin durabilidad | `config/environments/test.rb`, workflow de CI |

## Resultados locales

Cada fila agrega un cambio a la anterior. Los tiempos son de reloj para la suite completa, promedio de dos rondas limpias, en una notebook con un i7-1165G7 (4 núcleos, 8 hilos).

| # | Cambio | Segundos | Ahorro | Segundos de CPU |
|---|---|---|---|---|
| 0 | Un proceso (original) | **709** | | 672 |
| 1 | Paralelización | **259** | −450 | 1.344 |
| 2 | bcrypt al costo mínimo | **215** | −44 | 1.028 |
| 3 | Página de 404 barata | **188** | −27 | 883 |
| 4 | Sin SimpleCov | **169** | −19 | 753 |
| 5 | Sin progress reporter | **161** | −8 | 705 |
| 6 | Sin Bullet | 174 | dentro del ruido | 682 |
| 7 | Log level `warn` | **158** | −16 (respecto del paso 5) | 611 |
| 8 | Tablas unlogged | **~142** | −16 (A/B aparte) | 590 |

Notas sobre la tabla:

- **Ruido.** La diferencia entre corridas idénticas es de unos ±10 s. Los pasos 5 a 7 ahorran menos que eso en tiempo de reloj, pero el tiempo de CPU baja en cada uno: −48 s el reporter, −23 s Bullet y −71 s el log level.
- **La paralelización consume más CPU total** que un solo proceso (1.344 s contra 672 s) porque los dos hilos de cada núcleo compiten por él.
- **El paso 8 es una estimación**: los 158 s del paso 7 menos los 16 s que ahorraron las tablas unlogged en un A/B separado (ver más abajo). Los pasos 7 y 8 nunca se midieron en la misma corrida.

## Resultados en CI

El runner de GitHub Actions tiene 2 CPUs, así que los tests corren en 2 procesos.

| | Corridas | Tiempo de Minitest | Paso «Run tests» |
|---|---|---|---|
| **Antes** (sin cambios) | 39 | mediana **301 s** (183–410) | mediana 318 s |
| **Después** (todos los cambios) | 3 | mediana **143 s** (143, 149, 112) | mediana 160 s |

- **2,1× más rápido.** Con 2 procesos, paralelizar puede aportar como máximo 2×; el resto lo aportan los demás cambios.
- Las corridas «después» también tienen `fsync`, `synchronous_commit` y `full_page_writes` desactivados. Su efecto no se midió por separado.
- La cantidad de tests varía un poco (5.267–5.373 antes, 5.345 después) porque la rama principal sumó tests durante el día.
- En un solo proceso, CI fue más rápido que la notebook (unos 300 s contra 709 s): cada CPU del runner es más rápida que un núcleo de la notebook, que además baja su frecuencia bajo carga sostenida.

## Tiempo de reloj y tiempo de CPU

Los pasos 5 a 7 casi no mueven el reloj en la notebook, pero bajan el CPU de 753 s a 611 s. La diferencia se explica por cómo se reparte el trabajo:

- El **tiempo de reloj** es lo que espera la persona que corre los tests. Con workers en paralelo, lo determina el worker más lento y las esperas a la base de datos.
- El **tiempo de CPU** es el trabajo total de la máquina, sumado entre todos los procesos.
- Con núcleos de sobra, una sobrecarga por test se reparte entre núcleos que de otro modo estarían ociosos. La máquina trabaja menos, pero la espera no cambia.
- En un runner con 2 CPUs no hay núcleos ociosos: los dos workers y Postgres comparten las mismas dos CPUs. Cada segundo de CPU ahorrado se convierte casi directamente en un segundo de reloj. Por eso en CI la mejora (2,1×) supera lo que puede aportar la paralelización sola (2×).

Además, los minutos de CI suelen pagarse, y en una máquina de desarrollo ese CPU compite con el resto de los programas. Conviene medir las dos cosas: un cambio que no mueve el reloj en la notebook puede moverlo en CI, o cuando la suite crezca.

## Los ocho cambios

### 1. Paralelización (709 s → 259 s)

La línea `parallelize` que genera Rails estaba comentada desde el primer commit de la aplicación, así que la suite usaba 1 de los 8 hilos disponibles.

```ruby
# test/test_helper.rb
class ActiveSupport::TestCase
  parallelize(workers: :number_of_processors)
end
```

Cada worker usa su propia base de datos (`app_test_0`, `app_test_1`, …), que se reconstruye solo cuando cambia el schema. Hay que revisar el estado que comparten los procesos, como archivos en disco o contadores de throttling; en este caso hubo que reiniciar Rack::Attack en el `setup`.

Resultado: 2,7× más rápido descomentando una línea.

### 2. Costo de bcrypt (−44 s)

Devise ya usaba `config.stretches = Rails.env.test? ? 1 : 12`, pero esa opción solo afecta a Devise. El código de la aplicación llamaba directamente a `BCrypt::Password.create` para hashear códigos de firma de un solo uso, con el costo de producción (12). Un hash tardaba 1,6 s y el test más lento, 29 s.

```ruby
# test/test_helper.rb, después de require "rails/test_help"
BCrypt::Engine.cost = BCrypt::Engine::MIN_COST
```

Vale la pena buscar `BCrypt::Password.create` en cualquier aplicación.

### 3. La página de 404 (−27 s)

Con `consider_all_requests_local = true`, cada 404 renderizaba la página de error de desarrollo, que lista todas las rutas de la aplicación. Eso costaba unos 0,7 s por request. Una aplicación multi-tenant tiene muchos tests que verifican que un usuario ajeno recibe un 404, y todos pagaban ese costo.

```ruby
# config/environments/test.rb
config.consider_all_requests_local = false
```

### 4. Quitar SimpleCov (−19 s)

SimpleCov instrumenta cada línea de Ruby que se ejecuta, y al final tiene que combinar los resultados de los workers. Estaba siempre activo y nadie leía el reporte.

Se borraron la gema y el bloque `SimpleCov.start`. Para medir cobertura ocasionalmente: `require "simplecov" if ENV["COVERAGE"]`.

### 5. Quitar el progress reporter (−8 s, −7% de CPU)

La barra de progreso de `minitest-reporters` redibuja la terminal después de cada test. La salida por defecto de Minitest ya informa los errores. Se borraron la gema y la línea `Minitest::Reporters.use!`.

### 6. Quitar Bullet de los tests (−3% de CPU local; −16% en un benchmark de un proceso)

Bullet, el detector de N+1, inspecciona cada carga de ActiveRecord. Estaba configurado con `Bullet.raise = false`, así que nunca hacía fallar un test: solo escribía un log que nadie leía. Se quitó el bloque `Bullet.enable = true` de `config/environments/test.rb`. Si se usa `Bullet.raise = true`, tiene sentido mantenerlo y aceptar el costo.

### 7. Log level (−16 s, −10% de CPU)

En test, el nivel por defecto es `debug`: cada sentencia SQL se formatea y se escribe en `log/test.log`, que llega a ocupar gigabytes.

```ruby
# config/environments/test.rb
config.log_level = ENV.fetch("RAILS_LOG_LEVEL", "warn")
```

Para ver el SQL de un test puntual: `RAILS_LOG_LEVEL=debug bin/rails test path/to/test.rb`.

### 8. Postgres sin durabilidad (−16 s local, −10%)

Los datos de test se descartan al terminar cada corrida, así que no necesitan sobrevivir a un crash. La idea viene de un [tip de Dima Fatko (@fatkodima)](https://x.com/fatkodima/status/1740703726812406022).

**Tablas unlogged.** Postgres no escribe en el write-ahead log (WAL), el registro que usa para recuperarse de un crash, los cambios de estas tablas.

```ruby
# config/environments/test.rb
ActiveSupport.on_load(:active_record_postgresqladapter) do
  self.create_unlogged_tables = true
end
```

- La opción se aplica al crear la tabla, así que hay que borrar y recrear las bases de test existentes.
- `db:test:prepare` corre en el entorno de desarrollo, por lo que la base de test principal queda logged. Las bases de cada worker sí quedan unlogged.

**En CI, además**, se desactivan tres opciones de todo el servidor:

- `fsync = off`: Postgres no espera a que el sistema operativo confirme que los datos llegaron al disco. Ante un corte de energía, la base puede quedar corrupta.
- `synchronous_commit = off`: `COMMIT` responde antes de que su registro en el WAL esté en disco. Ante un crash se pierden las últimas transacciones confirmadas, pero la base sigue siendo consistente.
- `full_page_writes = off`: después de cada checkpoint, Postgres deja de copiar la página completa al WAL la primera vez que la modifica. Esa copia sirve para reparar páginas escritas a medias; sin ella el WAL es más chico, pero una escritura parcial no se puede recuperar.

Las tres cambian seguridad ante fallas por velocidad, y no deben usarse en producción. Se aplican solo en CI porque afectan a todo el servidor, y el Postgres local también aloja las bases de desarrollo. Complementan a las tablas unlogged: la base de test principal y el catálogo de Postgres siguen escribiendo WAL.

Un contenedor de servicio de GitHub Actions no acepta flags de línea de comandos, así que se aplican con `ALTER SYSTEM` y `pg_reload_conf()`. Ninguna requiere reiniciar el servidor.

```yaml
- name: Trade Postgres durability for speed
  run: |
    psql postgres://postgres:postgres@localhost:5432 \
      -c "ALTER SYSTEM SET fsync = off" \
      -c "ALTER SYSTEM SET synchronous_commit = off" \
      -c "ALTER SYSTEM SET full_page_writes = off" \
      -c "SELECT pg_reload_conf()"
```

## Medir bien: el caso de las tablas unlogged

La primera medición indicó que las tablas unlogged eran *más lentas*, algo improbable si la base hace menos trabajo. La causa: ese paso corría sobre bases recién creadas, sin estadísticas del planner y con la caché fría, mientras que los demás pasos reutilizaban bases ya calientes.

La prueba corregida usó dos juegos de bases calientes, uno logged y otro unlogged, ejecutó `ANALYZE` en ambos, alternó las variantes tres veces y verificó `relpersistence` antes de cada corrida (`p` = logged, `u` = unlogged):

| Corrida | Logged | Unlogged |
|---|---|---|
| 1 | 168 s | 150 s |
| 2 | 161 s | 156 s |
| 3 | 215 s | 152 s |
| **Mediana** | **168 s** | **152 s** |

Las tablas unlogged ahorran unos 16 s (−10%). El tiempo «Finished in» que informa Minitest es casi igual en ambos casos; la diferencia aparece fuera del loop de tests: las corridas logged pasan entre 47 y 108 s fuera de él, y las unlogged, entre 33 y 35 s.

Tres reglas que salen de esto:

1. **Medir en estado caliente**: bases ya creadas y con estadísticas.
2. **Alternar las variantes y repetir**. En una primera ronda con la máquina cargada, la misma configuración dio 403 s en una corrida y 202 s en la siguiente.
3. **Verificar que el cambio se aplicó**. En una ronda, el paso «unlogged» corrió sobre tablas logged por un error en el patrón de nombres de las bases.

## Metodología

- Cada cambio se activaba o desactivaba con una variable de entorno, en una copia aislada del repositorio (git worktree).
- La escalera de la tabla local corrió cuatro veces. Las rondas 1 y 2 se descartaron: la 1 tuvo carga externa alta y la 2 midió el paso unlogged sobre bases logged. La tabla promedia las rondas 3 y 4, que incluyen una corrida de calentamiento.
- El tiempo de un solo proceso (709 s) es de la ronda 1, con load average 4.
- Los datos de CI se obtuvieron con `gh api` y `gh run view --log`: duración de jobs y pasos, y el «Finished in», la cantidad de tests y la cantidad de workers que informa Minitest.

## Conclusiones

1. **Las mayores ganancias no estaban en los tests**, sino en la configuración: una línea comentada, un factor de costo y una opción de la página de errores.
2. **Cada cambio se mide por separado y más de una vez.** Una base recién creada hizo que una optimización real pareciera una regresión.
3. **El tiempo de reloj y el de CPU cuentan historias distintas.** Las sobrecargas chicas casi no se notan en una máquina con núcleos libres, pero aparecen en el CPU y en runners chicos de CI.
4. **Una herramienta que no puede hacer fallar el build solo cuesta tiempo**: cobertura que nadie lee, un Bullet que nunca falla, una barra de progreso.

## La receta completa

```ruby
# test/test_helper.rb
parallelize(workers: :number_of_processors)
BCrypt::Engine.cost = BCrypt::Engine::MIN_COST

# config/environments/test.rb
config.consider_all_requests_local = false
config.log_level = ENV.fetch("RAILS_LOG_LEVEL", "warn")
ActiveSupport.on_load(:active_record_postgresqladapter) do
  self.create_unlogged_tables = true
end
# Bullet.enable = true             (eliminado)

# Gemfile
# gem "simplecov"                  (eliminado)
# gem "minitest-reporters"         (eliminado)
```
