using System.Text.Json;
using Harness.Api.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.Extensions.Options;
using Npgsql.EntityFrameworkCore.PostgreSQL.Infrastructure;
using Wolverine.EntityFrameworkCore;

namespace Harness.Api.Infrastructure;

/// <summary>
/// The whole relational core, including the event stream — EF Core owns the <c>public</c>
/// schema end to end. There is no second store: no document/event database, no separate migration
/// engine to stay out of each other's way. The only other schema this system will ever grow is
/// <c>wolverine</c>, for messaging envelope storage, and only once messaging is actually built.
///
/// EF migrations, not a diff engine: a diff engine cannot express a data migration, and a system
/// whose whole justification is being an auditable source of truth should have a reviewable,
/// checked-in history of its own schema.
///
/// <para><b>Three tiers.</b> Landing
/// (<c>Provider*</c>) is what a provider stated, keyed on the provider's own ids. Internal
/// (<see cref="Client"/> / <see cref="Person"/>) is identity we own, which outlives any delivery.
/// Generic (<see cref="EntityType"/> / <see cref="Entity"/> / <see cref="EntityPair"/> /
/// <see cref="RelationshipType"/> / <see cref="Relationship"/>) carries every link that means
/// something beyond "these two records refer to each other".</para>
///
/// <para>The rule that sorts a link into a tier: a row pointing at the thing it is scoped under
/// is a foreign key (a benefit's policy); two records referring to each other with nothing to say
/// <i>about</i> the reference is a foreign key (an adviser's staff member); only a link that
/// carries a tag becomes a <see cref="Relationship"/> row. The invariant worth policing in
/// review is unchanged: an internal entity may not carry a provider column.</para>
/// </summary>
public class CrmDbContext(DbContextOptions<CrmDbContext> options): DbContext(options)
{
    // ── Internal: identity and composition. No provider knowledge anywhere below. ─────────
    public DbSet<Client> Clients => Set<Client>();
    public DbSet<Person> People => Set<Person>();

    // ── Landing: one row as a provider stated it. Append-only, shaped at the edge. ────────
    public DbSet<ProviderContact> ProviderContacts => Set<ProviderContact>();
    public DbSet<ProviderPolicy> ProviderPolicies => Set<ProviderPolicy>();
    public DbSet<ProviderBenefit> ProviderBenefits => Set<ProviderBenefit>();
    public DbSet<ProviderPolicyParty> ProviderPolicyParties => Set<ProviderPolicyParty>();
    public DbSet<ProviderAdviser> ProviderAdvisers => Set<ProviderAdviser>();

    // ── Staging: a delivery, and what reconciling it decided, before anything is applied. ─
    public DbSet<ImportBatch> ImportBatches => Set<ImportBatch>();
    public DbSet<ImportBatchSource> ImportBatchSources => Set<ImportBatchSource>();
    public DbSet<StagedRow> StagedRows => Set<StagedRow>();

    // ── Generic: the open vocabulary of linkable types, one row per registered IEntity, and
    // the tagged links between them. One link table serves every pair of types, because both
    // ends address `entity`, never a typed table's own key. ────────────────────────────────
    public DbSet<EntityType> EntityTypes => Set<EntityType>();
    public DbSet<Entity> Entities => Set<Entity>();
    public DbSet<EntityPair> EntityPairs => Set<EntityPair>();
    public DbSet<RelationshipType> RelationshipTypes => Set<RelationshipType>();
    public DbSet<Relationship> Relationships => Set<Relationship>();

    // ── Access control, work, and the event stream — the one append-only record. ──────────
    public DbSet<Workspace> Workspaces => Set<Workspace>();
    public DbSet<WorkspaceAssignment> WorkspaceAssignments => Set<WorkspaceAssignment>();
    public DbSet<Permission> Permissions => Set<Permission>();
    public DbSet<AppUser> AppUsers => Set<AppUser>();
    public DbSet<Event> Events => Set<Event>();
    public DbSet<Note> Notes => Set<Note>();
    public DbSet<TaskItem> Tasks => Set<TaskItem>();
    public DbSet<Pipeline> Pipelines => Set<Pipeline>();
    public DbSet<PipelineWorkspace> PipelineWorkspaces => Set<PipelineWorkspace>();
    public DbSet<IdempotencyRecord> IdempotencyRecords => Set<IdempotencyRecord>();
    public DbSet<PipelineStage> Stages => Set<PipelineStage>();
    public DbSet<FieldDefinition> FieldDefinitions => Set<FieldDefinition>();
    public DbSet<FieldOption> FieldOptions => Set<FieldOption>();
    public DbSet<FieldValue> FieldValues => Set<FieldValue>();
    public DbSet<Card> Cards => Set<Card>();
    public DbSet<ClientCard> ClientCards => Set<ClientCard>();
    public DbSet<TaskCard> TaskCards => Set<TaskCard>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        // Trigram search runs on the relational columns, so the extension is an EF concern
        // and lands in a migration. Global search must match a policy number as well as a
        // name — the policy number is the only identifier a client ever sees from their
        // insurer, so it is what staff search by when a renewal letter arrives.
        b.HasPostgresExtension("pg_trgm");

        // The HF number series. One shared sequence — not one per target type — so a Person, a
        // Client Grouping, a Policy and a Benefit all draw from the same series and the number
        // alone never has to say what type of thing it names. Explicit start/increment even though
        // they match the Postgres default, to make the choice visible rather than implicit.
        // Infrastructure/Persistence/HarnessNumberAllocator.cs is the one place it is read from.
        b.HasSequence<long>("harness_number_seq").StartsAt(1).IncrementsBy(1);

        // ═════════════════════════════════════════════════════════════════════════════════
        //  THE MODEL, one IEntityTypeConfiguration per entity type, grouped by tier into six
        //  files beside this one. Keeping OnModelCreating split this way is EF Core's own
        //  recommendation.
        //
        //  APPLIED EXPLICITLY, NOT BY ASSEMBLY SCAN. ApplyConfigurationsFromAssembly is the usual
        //  pairing, but the order in which it applies configurations is undefined, so it is only
        //  safe where order does not matter. It matters here: provider_benefit declares composite
        //  foreign keys onto the keys provider_contact and provider_policy configure. Listing them
        //  keeps that dependency visible in one place instead of resting on a guarantee the
        //  framework does not give.
        //
        //  A new entity type needs BOTH a DbSet above and a line here. That is deliberate — the
        //  scan would have made it one, at the cost of the ordering above.
        // ═════════════════════════════════════════════════════════════════════════════════

        // Internal — identity we own, which outlives any delivery.
        b.ApplyConfiguration(new ClientConfiguration());
        b.ApplyConfiguration(new PersonConfiguration());

        // Landing — one row as a provider stated it. Contact and policy precede benefit, which
        // references both.
        b.ApplyConfiguration(new ProviderContactConfiguration());
        b.ApplyConfiguration(new ProviderPolicyConfiguration());
        b.ApplyConfiguration(new ProviderBenefitConfiguration());
        b.ApplyConfiguration(new ProviderPolicyPartyConfiguration());
        b.ApplyConfiguration(new ProviderAdviserConfiguration());

        // Staging — the batch precedes its rows, which reference it.
        b.ApplyConfiguration(new ImportBatchConfiguration());
        b.ApplyConfiguration(new ImportBatchSourceConfiguration());
        b.ApplyConfiguration(new StagedRowConfiguration());

        // Generic — the linkable types, the entities, the vocabulary, and the links.
        b.ApplyConfiguration(new EntityTypeConfiguration());
        b.ApplyConfiguration(new EntityConfiguration());
        b.ApplyConfiguration(new EntityPairConfiguration());
        b.ApplyConfiguration(new RelationshipTypeConfiguration());
        b.ApplyConfiguration(new RelationshipConfiguration());

        // Access control and audit.
        b.ApplyConfiguration(new WorkspaceConfiguration());
        b.ApplyConfiguration(new WorkspaceAssignmentConfiguration());
        b.ApplyConfiguration(new PermissionConfiguration());
        b.ApplyConfiguration(new AppUserConfiguration());
        b.ApplyConfiguration(new EventConfiguration());

        // Work — notes, tasks, pipelines and the cards on them. Card precedes its two TPH
        // subclasses, which configure against the discriminator it declares.
        b.ApplyConfiguration(new NoteConfiguration());
        b.ApplyConfiguration(new IdempotencyConfiguration());
        b.ApplyConfiguration(new PipelineConfiguration());
        b.ApplyConfiguration(new PipelineStageConfiguration());
        b.ApplyConfiguration(new FieldDefinitionConfiguration());
        b.ApplyConfiguration(new FieldOptionConfiguration());
        b.ApplyConfiguration(new FieldValueConfiguration());
        b.ApplyConfiguration(new PipelineWorkspaceConfiguration());
        b.ApplyConfiguration(new CardConfiguration());
        b.ApplyConfiguration(new ClientCardConfiguration());
        b.ApplyConfiguration(new TaskCardConfiguration());
        b.ApplyConfiguration(new TaskItemConfiguration());

        // Wolverine's inbox/outbox envelope tables, mapped into THIS context. Under Lightweight
        // transaction mode there is no explicit transaction for Wolverine to enlist a second
        // connection in, so the only way a cascaded message lands atomically with the rows it
        // describes is for the same SaveChangesAsync to insert it — which is what this mapping
        // buys: Wolverine persists new messages through EF Core and rides its command batching.
        // The schema matches PersistMessagesWithPostgresql's in Program.cs. These entity types are
        // EXCLUDED from EF migrations by WolverineSchemaExcludedFromMigrationsConvention below:
        // Wolverine creates and owns that schema itself, and Harness.Api/CLAUDE.md's rule that a
        // migration never touches `wolverine` still holds.
        b.MapWolverineEnvelopeStorage(WolverineSchema);
    }

    /// <summary>The one schema EF does not own. Named once, read by the mapping above and the
    /// convention that keeps it out of migrations.</summary>
    public const string WolverineSchema = "wolverine";

    /// <summary>
    /// The provider options every registration of this context applies — Aspire in the host,
    /// the bare <c>UseNpgsql</c> in the test fixture, and the design-time factory. One method,
    /// three call sites, so a behaviour cannot differ between the host and the tests that are
    /// supposed to see what the host sees.
    ///
    /// <para><b>Not an <c>OnConfiguring</c> override.</b> That was tried first and it breaks the
    /// host silently: Aspire registers the context POOLED, EF refuses options changes from
    /// <c>OnConfiguring</c> under pooling, every host-side construction threw, and Wolverine's
    /// EF persistence provider — which instantiates the context to read its model — concluded it
    /// mapped nothing ("Could not determine a matching persistence service for entity
    /// Workspace"). The fixture's non-pooled context hid it from the unit tests.</para>
    ///
    /// <para>Split query is the default for every collection <c>Include</c>; a measured call
    /// site opts back in with <c>AsSingleQuery()</c>. The measurement that made it the default is
    /// on <c>ImportBatches.LoadAsync</c>: 116 s single-query against 179 ms split.</para>
    /// </summary>
    public static void ConfigureNpgsql(NpgsqlDbContextOptionsBuilder npgsql){
        npgsql.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery);
        npgsql.MigrationsHistoryTable("__EFMigrationsHistory", "migrations");

    }

    // Registered here, not called inline at the end of OnModelCreating: a finalizing convention
    // provably runs after every convention-created shadow FK and the TPH discriminator exist, so
    // there is no "entity type added after this ran" hazard to reason about. See
    // SnakeCaseNamingConvention's remarks.
    protected override void ConfigureConventions(ModelConfigurationBuilder configurationBuilder)
    {
        configurationBuilder.Conventions.Add(_ => new SnakeCaseNamingConvention());
        configurationBuilder.Conventions.Add(_ => new WolverineSchemaExcludedFromMigrationsConvention());

        // Every decimal in this schema, project-wide, not per-property. Without an explicit
        // precision, EF Core/Npgsql defaults to a bare `numeric` with no bound, which EF logs a
        // warning about; 18,4 is generous relative to every observed sample (four-figure premiums
        // to six-figure sums insured, two decimal places) without truncating a raw provider value
        // that happens to carry more.
        configurationBuilder.Properties<decimal>().HavePrecision(18, 4);
    }

    // protected override void OnConfiguring(DbContextOptionsBuilder options)
    // {
    //     // 1. Look for the Npgsql options extension
    //     var connectionString = _configuration.GetConnectionString("DefaultConnection");

    //     options.UseNpgsql(connectionString,
    //     x => x.MigrationsHistoryTable("__EFMigrationsHistory", "migrations"));
    // }
    /// <summary>
    /// <see cref="Person.FullName"/> carries the trigram index global search depends on, and
    /// nothing else keeps it in agreement with the name parts. Wolverine's EF Core transactional
    /// middleware calls one of the two <c>SaveChangesAsync</c> overloads for every write endpoint
    /// — both are independently virtual on <see cref="DbContext"/>, so this is the one with the
    /// real implementation; the other overload below forwards into it rather than into
    /// <c>base</c>, so the rule fires regardless of which overload the caller uses. Kept thin —
    /// the actual rule lives in <see cref="PersonName.Compose"/>, pure and unit-testable.
    /// </summary>
    public override Task<int> SaveChangesAsync(
        bool acceptAllChangesOnSuccess, CancellationToken cancellationToken = default)
    {
        // PersonName.Compose falls back to a supplied FullName because both provider exports
        // carry a single name field — a person populated from Asteron has a FullName and no
        // parts, and that is not an error state.
        foreach (var entry in ChangeTracker.Entries<Person>())
        {
            if (entry.State is EntityState.Added or EntityState.Modified)
                entry.Entity.FullName = PersonName.Compose(entry.Entity);
        }

        return base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken);
    }

    public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default) =>
        SaveChangesAsync(acceptAllChangesOnSuccess: true, cancellationToken);
}
