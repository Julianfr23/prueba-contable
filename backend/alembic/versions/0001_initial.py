"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    naturaleza_enum = pg.ENUM("debito", "credito", name="naturaleza_enum")
    estado_periodo_enum = pg.ENUM("abierto", "cerrado", name="estado_periodo_enum")
    estado_comprobante_enum = pg.ENUM(
        "borrador", "contabilizado", "reversado", "reversion", name="estado_comprobante_enum"
    )

    op.create_table(
        "empresas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("nit", sa.String(20), nullable=False, unique=True),
        sa.Column("razon_social", sa.String(255), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "cuentas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("naturaleza", naturaleza_enum, nullable=False),
        sa.Column("activa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_cuenta_empresa_codigo"),
    )
    op.create_index("ix_cuentas_codigo", "cuentas", ["codigo"])

    op.create_table(
        "periodos_contables",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("anio", sa.Integer, nullable=False),
        sa.Column("mes", sa.Integer, nullable=False),
        sa.Column("estado", estado_periodo_enum, nullable=False, server_default="abierto"),
        sa.Column("cerrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("empresa_id", "anio", "mes", name="uq_periodo_empresa_anio_mes"),
    )

    op.create_table(
        "correlativos",
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), primary_key=True),
        sa.Column("ultimo_numero", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "terceros",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("tipo_doc", sa.String(10), nullable=False, server_default="CC"),
        sa.Column("num_doc", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.UniqueConstraint("empresa_id", "tipo_doc", "num_doc", name="uq_tercero_doc"),
    )

    op.create_table(
        "comprobantes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=True),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column(
            "periodo_id", pg.UUID(as_uuid=True), sa.ForeignKey("periodos_contables.id"), nullable=False
        ),
        sa.Column("descripcion", sa.Text, nullable=False),
        sa.Column("estado", estado_comprobante_enum, nullable=False, server_default="borrador"),
        sa.Column(
            "comprobante_original_id", pg.UUID(as_uuid=True), sa.ForeignKey("comprobantes.id"), nullable=True
        ),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("contabilizado_en", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "lineas_contables",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "comprobante_id", pg.UUID(as_uuid=True), sa.ForeignKey("comprobantes.id"), nullable=False
        ),
        sa.Column("cuenta_id", pg.UUID(as_uuid=True), sa.ForeignKey("cuentas.id"), nullable=False),
        sa.Column("tercero_id", pg.UUID(as_uuid=True), sa.ForeignKey("terceros.id"), nullable=True),
        sa.Column("debito", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credito", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("descripcion", sa.Text, nullable=True),
    )
    op.create_index("ix_lineas_cuenta_id", "lineas_contables", ["cuenta_id"])
    op.create_index("ix_lineas_comprobante_id", "lineas_contables", ["comprobante_id"])

    op.create_table(
        "uvt_valores",
        sa.Column("anio", sa.Integer, primary_key=True),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("fuente", sa.String(50), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "uvt_actualizacion_log",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("anio", sa.Integer, nullable=False),
        sa.Column("exitoso", sa.Boolean, nullable=False),
        sa.Column("detalle", sa.Text, nullable=False),
        sa.Column("intentos", sa.Integer, nullable=False, server_default="1"),
        sa.Column("ejecutado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "exogena_generaciones",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("empresa_id", pg.UUID(as_uuid=True), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("anio_gravable", sa.Integer, nullable=False),
        sa.Column("umbral_uvt", sa.Numeric(14, 2), nullable=False),
        sa.Column("uvt_valor_usado", sa.Numeric(14, 2), nullable=False),
        sa.Column("xml_contenido", sa.Text, nullable=False),
        sa.Column("total_registros", sa.Integer, nullable=False),
        sa.Column("total_valor_bruto", sa.Numeric(18, 2), nullable=False),
        sa.Column("generado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("exogena_generaciones")
    op.drop_table("uvt_actualizacion_log")
    op.drop_table("uvt_valores")
    op.drop_table("lineas_contables")
    op.drop_table("comprobantes")
    op.drop_table("terceros")
    op.drop_table("correlativos")
    op.drop_table("periodos_contables")
    op.drop_table("cuentas")
    op.drop_table("empresas")
    sa.Enum(name="estado_comprobante_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="estado_periodo_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="naturaleza_enum").drop(op.get_bind(), checkfirst=True)
