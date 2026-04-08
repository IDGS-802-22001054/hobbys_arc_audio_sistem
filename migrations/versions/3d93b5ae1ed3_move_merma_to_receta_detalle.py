"""move merma to receta detalle

Revision ID: 3d93b5ae1ed3
Revises: 
Create Date: 2026-04-05 09:37:58.661461

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d93b5ae1ed3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "RecetaDetalle",
        sa.Column("Merma", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    receta_columns = {column["name"] for column in inspector.get_columns("Receta")}

    if "Merma" in receta_columns:
        recetas_con_merma = bind.execute(
            sa.text(
                """
                SELECT IdProductoTerminado, Merma
                FROM Receta
                WHERE COALESCE(Merma, 0) > 0
                """
            )
        ).fetchall()

        for producto_id, merma in recetas_con_merma:
            detalle_id = bind.execute(
                sa.text(
                    """
                    SELECT rd.IdRecetaDetalle
                    FROM RecetaDetalle rd
                    INNER JOIN MateriaPrima mp
                        ON mp.IdMateriaPrima = rd.IdMateriaPrima
                    INNER JOIN UnidadMedida um
                        ON um.IdUnidadMedida = mp.IdUnidadMedida
                    WHERE rd.IdProductoTerminado = :producto_id
                      AND LOWER(COALESCE(um.Abreviatura, '')) = 'ml'
                    ORDER BY rd.IdRecetaDetalle
                    LIMIT 1
                    """
                ),
                {"producto_id": producto_id},
            ).scalar()

            if detalle_id is None:
                detalle_id = bind.execute(
                    sa.text(
                        """
                        SELECT IdRecetaDetalle
                        FROM RecetaDetalle
                        WHERE IdProductoTerminado = :producto_id
                        ORDER BY IdRecetaDetalle
                        LIMIT 1
                        """
                    ),
                    {"producto_id": producto_id},
                ).scalar()

            if detalle_id is not None:
                bind.execute(
                    sa.text(
                        """
                        UPDATE RecetaDetalle
                        SET Merma = :merma
                        WHERE IdRecetaDetalle = :detalle_id
                        """
                    ),
                    {"merma": merma, "detalle_id": detalle_id},
                )

        op.drop_column("Receta", "Merma")

    _recalcular_costos(bind, include_merma=True)


def downgrade():
    op.add_column(
        "Receta",
        sa.Column("Merma", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
    )

    bind = op.get_bind()
    detalle_columns = {column["name"] for column in sa.inspect(bind).get_columns("RecetaDetalle")}

    if "Merma" in detalle_columns:
        totales_merma = bind.execute(
            sa.text(
                """
                SELECT IdProductoTerminado, COALESCE(SUM(Merma), 0) AS MermaTotal
                FROM RecetaDetalle
                GROUP BY IdProductoTerminado
                """
            )
        ).fetchall()

        for producto_id, merma_total in totales_merma:
            bind.execute(
                sa.text(
                    """
                    UPDATE Receta
                    SET Merma = :merma_total
                    WHERE IdProductoTerminado = :producto_id
                    """
                ),
                {"merma_total": merma_total, "producto_id": producto_id},
            )

        op.drop_column("RecetaDetalle", "Merma")

    _recalcular_costos(bind, include_merma=False)


def _recalcular_costos(bind, include_merma):
    bind.execute(sa.text("UPDATE ProductoTerminado SET CostoProduccion = 0"))

    expresion_consumo = "rd.CantidadRequerida + COALESCE(rd.Merma, 0)" if include_merma else "rd.CantidadRequerida"
    costos = bind.execute(
        sa.text(
            f"""
            SELECT
                rd.IdProductoTerminado,
                COALESCE(
                    SUM(
                        ({expresion_consumo}) *
                        CASE
                            WHEN LOWER(COALESCE(um.Abreviatura, '')) IN ('g', 'ml')
                                THEN COALESCE(mp.PrecioUnitario, 0) / 1000
                            ELSE COALESCE(mp.PrecioUnitario, 0)
                        END
                    ),
                    0
                ) AS Total
            FROM RecetaDetalle rd
            LEFT JOIN MateriaPrima mp
                ON mp.IdMateriaPrima = rd.IdMateriaPrima
            LEFT JOIN UnidadMedida um
                ON um.IdUnidadMedida = mp.IdUnidadMedida
            GROUP BY rd.IdProductoTerminado
            """
        )
    ).fetchall()

    for producto_id, total in costos:
        bind.execute(
            sa.text(
                """
                UPDATE ProductoTerminado
                SET CostoProduccion = :total
                WHERE IdProductoTerminado = :producto_id
                """
            ),
            {"total": total, "producto_id": producto_id},
        )
