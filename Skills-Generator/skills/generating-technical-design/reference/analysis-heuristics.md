## Contents
- Node.js & TypeScript Frameworks
- Python Frameworks
- Go Frameworks
- Rust Frameworks
- Java & Kotlin Frameworks
- Ruby & Rails Frameworks
- Data Persistence & Migration Heuristics
- Asynchronous Workers & Event Consumers

---

## Node.js & TypeScript Frameworks

### Express / Fastify / Koa
- **Route Definitions:** Search for `app.use(`, `router.get(`, `router.post(`, `fastify.route(`, or `route.register(`.
- **Controllers & Handlers:** Follow handler arguments `(req: Request, res: Response, next: NextFunction)`.
- **Middleware:** Look for `passport.authenticate(`, `cors()`, `express.json()`, `zod`/`joi` validation middleware.
- **Entry Points:** `src/server.ts`, `src/app.ts`, `src/index.ts`, `bin/www`.

### NestJS
- **Modules & Dependency Injection:** Look for `@Module({ imports: [], controllers: [], providers: [] })`.
- **Controllers & Routes:** Look for `@Controller('prefix')`, `@Get()`, `@Post()`, `@UseGuards()`.
- **Data Models:** Look for `@Entity()`, `@Column()` (TypeORM) or `@Schema()`, `@Prop()` (Mongoose) or Prisma schema definitions.

### Next.js / Remix (Full-Stack / SSR)
- **Next.js App Router:** Inspect `app/**/route.ts` (API routes) and `app/**/page.tsx` (Server Components).
- **Next.js Pages Router:** Inspect `pages/api/**/*.ts`.
- **Server Actions:** Inspect files with `'use server'` directive.

---

## Python Frameworks

### FastAPI
- **Entry & Routers:** Look for `FastAPI()`, `app.include_router(router, prefix="/api/v1")`, `APIRouter()`.
- **Endpoints & Types:** `@router.get(...)`, `@router.post(...)`, typing inputs with Pydantic `BaseModel`.
- **Dependency Injection:** Search for `Depends(...)` in route signatures (database sessions, auth guards).

### Django & Django REST Framework (DRF)
- **URL Routing:** Check `urlpatterns = [...]` in `urls.py` across app directories.
- **Views & ViewSets:** Look for `class ResourceViewSet(viewsets.ModelViewSet)`, `@api_view(['GET', 'POST'])`.
- **ORM Models:** Check `models.Model` subclasses in `models.py`.
- **Serializers:** Check `serializers.ModelSerializer` in `serializers.py`.

### Flask
- **Blueprints & Routes:** Search for `Blueprint(...)`, `@bp.route(...)`, `@app.route(...)`.
- **ORM & Extensions:** SQLAlchemy models inheriting from `db.Model`, Marshmallow schemas.

---

## Go Frameworks

### Gin / Echo / Fiber / Chi / Standard Library (`net/http`)
- **Routing & Groups:** Search for `r.Group("/api/v1")`, `router.POST("/path", handler)`, `chi.NewRouter()`, `http.HandleFunc`.
- **Entry Point:** Locate `main.go` and trace initialization of server structs, middleware chaining, and handler bindings.
- **Structs & Schemas:** Inspect Go structs with JSON and DB tags (e.g., `` `json:"user_id" gorm:"primaryKey"` ``).
- **Interfaces & Domain Repositories:** Look for interface declarations defining storage or service contracts (e.g., `type UserRepository interface { ... }`).

---

## Rust Frameworks

### Actix-web / Axum / Rocket
- **Axum:** Look for `Router::new().route("/path", get(handler).post(handler))`.
- **Actix-web:** Look for `#[get("/path")]`, `#[post("/path")]`, `App::new().service(...)`.
- **Rocket:** Look for `#[get("/path")]`, `rocket::build().mount("/", routes![...])`.
- **Models & Serialization:** Look for structs deriving `#[derive(Serialize, Deserialize, sqlx::FromRow)]`.

---

## Java & Kotlin Frameworks

### Spring Boot
- **Controllers:** `@RestController`, `@RequestMapping("/api/v1")`, `@GetMapping`, `@PostMapping`.
- **Services & Repositories:** `@Service`, `@Component`, `@Repository`, interfaces extending `JpaRepository<T, ID>`.
- **Entities & Validation:** `@Entity`, `@Table(name = "...")`, `@Valid`, `@NotNull`.
- **Security:** Look for `SecurityFilterChain` beans and `@PreAuthorize` annotations.

---

## Ruby & Rails Frameworks

### Ruby on Rails
- **Routes:** `config/routes.rb` containing `resources :orders`, `namespace :api do ...`.
- **Controllers:** `app/controllers/**/*_controller.rb` inheriting from `ApplicationController` or `ActionController::API`.
- **Models:** `app/models/**/*.rb` inheriting from `ApplicationRecord` or `ActiveRecord::Base` with `has_many`, `belongs_to`.

---

## Data Persistence & Migration Heuristics

To reconstruct database schemas and entity relationships, search the following paths:
- **Prisma:** `prisma/schema.prisma`
- **TypeORM / MikrORM:** `src/entities/*.ts`, `src/migrations/*.ts`
- **SQLAlchemy / Alembic:** `alembic/versions/*.py`, `models/*.py`
- **Django Migrations:** `<app>/migrations/*.py`
- **Go Migrate / Goose / GORM:** `migrations/*.sql`, `db/migrations/*.sql`
- **Flyway / Liquibase:** `src/main/resources/db/migration/*.sql`
- **Raw SQL / DDL:** `schema.sql`, `init.sql`, `docker-entrypoint-initdb.d/`

---

## Asynchronous Workers & Event Consumers

Search for message queue clients, background tasks, and event stream listeners:
- **Celery / Python RQ:** `@celery.task`, `@shared_task`, `celery.py`, `tasks.py`.
- **BullMQ / Bull / Sidekiq:** `new Worker('queueName', async (job) => { ... })`, `include Sidekiq::Worker`.
- **Kafka / RabbitMQ / SQS:**
  - Node: `kafkajs`, `amqplib`, `@aws-sdk/client-sqs`
  - Go: `confluent-kafka-go`, `segmentio/kafka-go`, `rabbitmq/amqp091-go`, `aws/aws-sdk-go`
  - Python: `aiokafka`, `pika`, `boto3.client('sqs')`
  - Java: `@KafkaListener`, `@RabbitListener`, `JmsListener`
