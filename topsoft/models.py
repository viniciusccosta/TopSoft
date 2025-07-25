import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from sqlmodel import (
    JSON,
    Column,
    Field,
    Relationship,
    Session,
    SQLModel,
    UniqueConstraint,
    select,
)

logger = logging.getLogger(__name__)


from sqlalchemy import JSON


class BaseModel(SQLModel):
    """Base model with common CRUD operations - Django-style ActiveRecord pattern"""

    @classmethod
    def _get_session(cls) -> Session:
        """Get database session - imported here to avoid circular imports"""
        from topsoft.database import get_session

        return get_session()

    @classmethod
    def create(cls, **kwargs) -> "BaseModel":
        """Create and save a new instance"""
        session = cls._get_session()
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance

    @classmethod
    def get_by_id(cls, id: int) -> Optional["BaseModel"]:
        """Get instance by ID"""
        session = cls._get_session()
        return session.get(cls, id)

    @classmethod
    def get_all(cls) -> List["BaseModel"]:
        """Get all instances"""
        session = cls._get_session()
        statement = select(cls)
        return session.exec(statement).all()

    @classmethod
    def filter_by(cls, **kwargs) -> List["BaseModel"]:
        """Filter instances by given criteria"""
        session = cls._get_session()
        statement = select(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)
        return session.exec(statement).all()

    @classmethod
    def get_or_create(cls, defaults=None, **kwargs) -> tuple["BaseModel", bool]:
        """Get instance or create if it doesn't exist"""
        session = cls._get_session()
        statement = select(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)

        instance = session.exec(statement).first()
        if instance:
            return instance, False
        else:
            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)
            instance = cls.create(**create_kwargs)
            return instance, True

    def save(self) -> "BaseModel":
        """Save current instance"""
        session = self._get_session()
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def update(self, **kwargs) -> "BaseModel":
        """Update current instance"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.save()

    def delete(self) -> None:
        """Delete current instance"""
        session = self._get_session()
        session.delete(self)
        session.commit()


class Aluno(BaseModel, table=True):
    id: Optional[int] = Field(
        default=None,  # Default to None for auto-increment
        primary_key=True,
    )

    # API:
    nome: str

    matricula: Optional[str] = None
    responsavel_id: Optional[int] = None

    cpf: Optional[str] = None
    sexo: Optional[str] = None
    data_nascimento: Optional[datetime] = None
    celular: Optional[str] = None
    email: Optional[str] = None
    url_foto: Optional[str] = None

    responsavel_secundario_id: Optional[int] = None
    filiacao_1_id: Optional[int] = None
    filiacao_2_id: Optional[int] = None
    cartao_acesso: Optional[str] = None
    unidade_id: Optional[int] = None
    tipo_liberacao: Optional[str] = None
    foto_data_hora_alteracao: Optional[datetime] = None
    # cartao_acesso_data_alteracao: Optional[datetime] = None

    responsaveis_adicionais_ids: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    id_turmas: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )

    # Relationships:
    cartoes_acesso: List["CartaoAcesso"] = Relationship(
        back_populates="aluno",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # Custom model-specific methods
    @classmethod
    def get_all(cls, sort_by=None, offset=None, limit=None) -> List["Aluno"]:
        """Get all students with optional sorting and pagination"""
        try:
            session = cls._get_session()
            statement = select(cls)

            # Apply sorting at database level if possible
            if sort_by and hasattr(cls, sort_by):
                statement = statement.order_by(getattr(cls, sort_by))

            # Apply pagination at database level
            if offset is not None:
                statement = statement.offset(offset)
            if limit is not None:
                statement = statement.limit(limit)

            alunos = session.exec(statement).all()

            # Fallback to Python sorting if not applied at DB level
            if sort_by and hasattr(cls, sort_by) and offset is None and limit is None:
                alunos = sorted(alunos, key=lambda x: getattr(x, sort_by) or "")

            return alunos
        except Exception as e:
            logger.error(f"Error fetching alunos: {e}")
            return []

    @classmethod
    def find_by_name(cls, nome: str) -> Optional["Aluno"]:
        """Find student by exact name"""
        nome = nome.strip()
        try:
            results = cls.filter_by(nome=nome)
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Error fetching Aluno by name {nome}: {e}")
            return None

    @classmethod
    def find_by_matricula(cls, matricula: str) -> Optional["Aluno"]:
        """Find student by matricula"""
        session = cls._get_session()
        statement = select(cls).where(cls.matricula == matricula)
        return session.exec(statement).first()

    @classmethod
    def find_by_cpf(cls, cpf: str) -> Optional["Aluno"]:
        """Find student by CPF"""
        session = cls._get_session()
        statement = select(cls).where(cls.cpf == cpf)
        return session.exec(statement).first()

    @classmethod
    def search_by_name(cls, name_part: str) -> List["Aluno"]:
        """Search students by name (partial match)"""
        session = cls._get_session()
        statement = select(cls).where(cls.nome.ilike(f"%{name_part}%"))
        return session.exec(statement).all()

    def add_cartao_acesso(self, numeracao: str) -> "CartaoAcesso":
        """Add a new access card to this student"""
        cartao = CartaoAcesso.create(numeracao=numeracao, aluno_id=self.id)
        return cartao

    def get_active_cartoes(self) -> List["CartaoAcesso"]:
        """Get all active access cards for this student"""
        return [cartao for cartao in self.cartoes_acesso if cartao.aluno_id == self.id]

    def get_recent_acessos(self, days: int = 30) -> List["Acesso"]:
        """Get recent access records for this student"""
        session = self._get_session()
        cutoff_date = date.today() - timedelta(days=days)
        cartao_ids = [cartao.id for cartao in self.cartoes_acesso]
        if not cartao_ids:
            return []

        statement = select(Acesso).where(
            Acesso.cartao_acesso_id.in_(cartao_ids), Acesso.date >= cutoff_date
        )
        return session.exec(statement).all()

    @classmethod
    def get_or_create(cls, defaults=None, **kwargs) -> tuple["Aluno", bool]:
        """Enhanced get_or_create that handles Aluno-specific logic"""
        # Handle nome-based lookup with additional kwargs support
        session = cls._get_session()

        # Drop unknown kwargs for database operations
        valid_kwargs = {k: v for k, v in kwargs.items() if hasattr(cls, k)}

        # Try to find existing student
        statement = select(cls)
        for key, value in valid_kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)

        instance = session.exec(statement).first()
        if instance:
            return instance, False
        else:
            # Create new student
            create_kwargs = valid_kwargs.copy()
            if defaults:
                # Only add defaults that are valid model fields
                valid_defaults = {k: v for k, v in defaults.items() if hasattr(cls, k)}
                create_kwargs.update(valid_defaults)

            instance = cls.create(**create_kwargs)
            return instance, True

    @classmethod
    def bulk_update_from_json(cls, alunos_json: List[dict]) -> None:
        """Bulk update student records from JSON data (typically from API sync)"""
        session = cls._get_session()

        try:
            for data in alunos_json:
                # Convert date string to datetime if needed
                if data.get("data_nascimento"):
                    try:
                        data["data_nascimento"] = datetime.fromisoformat(
                            data["data_nascimento"]
                        )
                    except ValueError:
                        pass  # leave as-is or set None

                # Build or update the Aluno instance
                aluno = session.get(cls, data["id"])
                if aluno:
                    # Update existing student
                    for key, val in data.items():
                        if hasattr(cls, key):
                            setattr(aluno, key, val)
                else:
                    # Create new student
                    valid_data = {
                        key: val for key, val in data.items() if hasattr(cls, key)
                    }
                    aluno = cls(**valid_data)
                    session.add(aluno)

            session.commit()
            logger.info(f"Synced {len(alunos_json)} alunos.")

        except Exception as e:
            logger.error(f"Error bulk updating students from JSON: {e}")
            session.rollback()
            raise

    # ...existing code...


class CartaoAcesso(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # API:
    # TODO: Deveríamos garantir que sempre será com 0s à esquerda !
    numeracao: str = Field(unique=True)  # str(5) ou str(16)

    # Relationships:
    aluno_id: Optional[int] = Field(default=None, foreign_key="aluno.id")
    aluno: Optional[Aluno] = Relationship(back_populates="cartoes_acesso")

    acessos: List["Acesso"] = Relationship(back_populates="cartao_acesso")

    @classmethod
    def get_all(cls) -> List["CartaoAcesso"]:
        """Get all access cards with their associated students"""
        try:
            from sqlalchemy.orm import joinedload

            session = cls._get_session()
            statement = select(cls).options(joinedload(cls.aluno))
            return session.exec(statement).all()
        except Exception as e:
            logger.error(f"Error fetching cartoes de acesso: {e}")
            return []

    @staticmethod
    def from_string(data: str) -> Optional["CartaoAcesso"]:
        """
        Creates a CartaoAcesso instance from a string.
        """
        try:
            numeracao = data[:16].strip()
            return CartaoAcesso(numeracao=numeracao)
        except Exception as e:
            logger.error(f"Error parsing CartaoAcesso from string: {e}")
            return None

    @classmethod
    def find_by_numeracao(cls, numeracao: str) -> Optional["CartaoAcesso"]:
        """Find access card by numeracao"""
        session = cls._get_session()
        statement = select(cls).where(cls.numeracao == numeracao)
        return session.exec(statement).first()

    @classmethod
    def get_unassigned(cls) -> List["CartaoAcesso"]:
        """Get all unassigned access cards"""
        session = cls._get_session()
        statement = select(cls).where(cls.aluno_id.is_(None))
        return session.exec(statement).all()

    def get_recent_acessos(self, days: int = 30) -> List["Acesso"]:
        """Get recent access records for this card"""
        session = self._get_session()
        cutoff_date = date.today() - timedelta(days=days)
        statement = select(Acesso).where(
            Acesso.cartao_acesso_id == self.id, Acesso.date >= cutoff_date
        )
        return session.exec(statement).all()

    def assign_to_aluno(self, aluno_id: int) -> "CartaoAcesso":
        """Assign this card to a student"""
        return self.update(aluno_id=aluno_id)

    def unassign(self) -> "CartaoAcesso":
        """Unassign this card from any student"""
        return self.update(aluno_id=None)

    @classmethod
    def get_or_create(cls, defaults=None, **kwargs) -> tuple["CartaoAcesso", bool]:
        """Enhanced get_or_create that handles CartaoAcesso-specific logic"""
        session = cls._get_session()

        # Ensure numeracao is properly formatted with leading zeros
        if "numeracao" in kwargs:
            # TODO: Make this configurable (16 or 5 characters)
            kwargs["numeracao"] = str(kwargs["numeracao"]).zfill(16)

        # Try to find existing card
        statement = select(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)

        instance = session.exec(statement).first()
        if instance:
            return instance, False
        else:
            # Create new card
            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)

            instance = cls.create(**create_kwargs)
            return instance, True

    @classmethod
    def get_or_create_by_numeracao(cls, numeracao: str) -> "CartaoAcesso":
        """Get or create access card by numeracao"""
        card, created = cls.get_or_create(numeracao=numeracao)
        return card

    @classmethod
    def bulk_create_missing(cls, numeracoes: List[str]) -> List["CartaoAcesso"]:
        """Create multiple cards if they don't exist"""
        session = cls._get_session()

        # Get existing cards
        statement = select(cls).where(cls.numeracao.in_(numeracoes))
        existing_cards = session.exec(statement).all()
        existing_numeracoes = {card.numeracao for card in existing_cards}

        # Create missing cards
        missing_numeracoes = set(numeracoes) - existing_numeracoes
        if missing_numeracoes:
            new_cards = [cls(numeracao=num) for num in missing_numeracoes]
            session.add_all(new_cards)
            session.commit()

            # Refresh to get IDs
            for card in new_cards:
                session.refresh(card)

            return new_cards
        return []

    # ...existing code...


class Acesso(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # API:
    marcacao: str  # "010"=Entrada, "011"=Saída
    date: date  # dd/mm/yy ou dd/mm/yyyy
    time: time  # hh:mm
    catraca: str  # str(2) = 01, 02, 03, ..., 99
    # "sequencial": # str(10)

    # Extra Fields:
    synced: Optional[bool] = Field(default=False)

    # Relationships:
    cartao_acesso_id: Optional[int] = Field(default=None, foreign_key="cartaoacesso.id")
    cartao_acesso: Optional[CartaoAcesso] = Relationship(back_populates="acessos")

    # Unique:
    __table_args__ = (
        UniqueConstraint(
            "marcacao",
            "date",
            "time",
            "catraca",
            "cartao_acesso_id",
            name="uq_acesso_marcacao_date_time_cat_cartao",
            comment="Unique constraint for Acesso table",
        ),
    )

    # Custom model-specific methods
    @classmethod
    def get_all(cls, offset=None, limit=None) -> List["Acesso"]:
        """Get all access records with pagination, ordered from most recent to oldest"""
        try:
            from sqlalchemy.orm import joinedload

            session = cls._get_session()
            statement = (
                select(cls)
                .options(joinedload(cls.cartao_acesso))
                .order_by(cls.date.desc(), cls.time.desc())
            )

            # Apply pagination if specified
            if offset is not None:
                statement = statement.offset(offset)
            if limit is not None:
                statement = statement.limit(limit)

            return session.exec(statement).all()
        except Exception as e:
            logger.error(f"Error fetching acessos: {e}")
            return []

    @classmethod
    def get_unsynced(cls) -> List["Acesso"]:
        """Get all unsynced access records with related cartao_acesso and aluno eagerly loaded"""
        from sqlalchemy.orm import joinedload

        session = cls._get_session()
        statement = (
            select(cls)
            .where(cls.synced == False)
            .options(joinedload(cls.cartao_acesso).joinedload(CartaoAcesso.aluno))
        )
        return session.exec(statement).all()

    @classmethod
    def get_by_date_range(cls, start_date: "date", end_date: "date") -> List["Acesso"]:
        """Get access records within date range"""
        session = cls._get_session()
        statement = select(cls).where(cls.date >= start_date, cls.date <= end_date)
        return session.exec(statement).all()

    @classmethod
    def get_by_cartao(cls, cartao_id: int) -> List["Acesso"]:
        """Get all access records for a specific card"""
        session = cls._get_session()
        statement = select(cls).where(cls.cartao_acesso_id == cartao_id)
        return session.exec(statement).all()

    def mark_synced(self) -> "Acesso":
        """Mark this access record as synced"""
        return self.update(synced=True)

    @classmethod
    def bulk_mark_synced(cls, access_ids: List[int]) -> None:
        """Mark multiple access records as synced"""
        session = cls._get_session()
        statement = select(cls).where(cls.id.in_(access_ids))
        records = session.exec(statement).all()
        for record in records:
            record.synced = True
            session.add(record)
        session.commit()

    @classmethod
    def get_entries_exits_by_date(cls, target_date: "date") -> dict:
        """Get count of entries and exits for a specific date"""
        session = cls._get_session()
        statement = select(cls).where(cls.date == target_date)
        records = session.exec(statement).all()

        entries = sum(1 for r in records if r.marcacao == "010")
        exits = sum(1 for r in records if r.marcacao == "011")

        return {"entries": entries, "exits": exits, "total": len(records)}

    @classmethod
    def update_by_id(cls, acesso_id: int, **kwargs) -> bool:
        """Update an access record by its ID"""
        try:
            session = cls._get_session()
            acesso = session.get(cls, acesso_id)
            if not acesso:
                logger.error(f"Acesso with ID {acesso_id} not found.")
                return False

            for key, value in kwargs.items():
                if hasattr(acesso, key):
                    setattr(acesso, key, value)

            session.add(acesso)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating acesso {acesso_id}: {e}")
            return False

    @classmethod
    def bulk_update(cls, acessos: List["Acesso"]) -> bool:
        """Bulk update access records in the database"""
        if not acessos:
            logger.warning("No access records to update.")
            return False

        try:
            session = cls._get_session()
            session.add_all(acessos)
            session.commit()
            logger.info(f"Updated {len(acessos)} access records successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to bulk update access records: {e}")
            session.rollback()
            return False

    @classmethod
    def bulk_update_synced_status(cls, acessos: List["Acesso"], status: bool) -> bool:
        """Bulk update the synced status of access records"""
        if not acessos:
            logger.warning("No access records to update.")
            return False

        try:
            session = cls._get_session()
            for acesso in acessos:
                acesso.synced = status
                session.add(acesso)
            session.commit()
            logger.info(f"Updated {len(acessos)} access records to synced={status}.")
            return True
        except Exception as e:
            logger.error(f"Failed to bulk update access records: {e}")
            session.rollback()
            return False

    @classmethod
    def bulk_update_synced_simple(cls, acessos) -> None:
        """Simple bulk update for synced status (legacy compatibility)"""
        try:
            session = cls._get_session()
            for acesso in acessos:
                acesso.synced = True
                session.add(acesso)
            session.commit()
            logger.info(f"Updated {len(acessos)} access records as synced.")
        except Exception as e:
            logger.error(f"Failed to bulk update synced status: {e}")
            session.rollback()

    @classmethod
    def get_existing_access(
        cls, cartao_id: int, date_obj: "date", time_obj: "time"
    ) -> Optional["Acesso"]:
        """Check if access record already exists"""
        session = cls._get_session()
        statement = select(cls).where(
            cls.cartao_acesso_id == cartao_id,
            cls.date == date_obj,
            cls.time == time_obj,
        )
        return session.exec(statement).first()

    @classmethod
    def create_access_record(
        cls,
        marcacao: str,
        date_obj: "date",
        time_obj: "time",
        catraca: str,
        cartao_id: int,
    ) -> "Acesso":
        """Create a new access record"""
        return cls.create(
            marcacao=marcacao,
            date=date_obj,
            time=time_obj,
            catraca=catraca,
            cartao_acesso_id=cartao_id,
            synced=False,
        )

    @classmethod
    def bulk_create_access_records(cls, access_data: List[dict]) -> List["Acesso"]:
        """Bulk create access records"""
        if not access_data:
            return []

        session = cls._get_session()
        new_records = []

        for data in access_data:
            record = cls(
                marcacao=data["marcacao"],
                date=data["date"],
                time=data["time"],
                catraca=data["catraca"],
                cartao_acesso_id=data["cartao_id"],
                synced=False,
            )
            new_records.append(record)

        session.add_all(new_records)
        session.commit()

        # Refresh to get IDs
        for record in new_records:
            session.refresh(record)

        return new_records

    def __repr__(self):
        return (
            f"Acesso(id={self.id}, marcacao='{self.marcacao}', date='{self.date}', "
            f"time='{self.time}', catraca='{self.catraca}', cartao_acesso_id={self.cartao_acesso_id})"
        )

    def __str__(self):
        # try:
        #     cartao_info = self.cartao_acesso.numeracao if self.cartao_acesso else "N/A"
        # except (AttributeError, Exception):
        #     cartao_info = str(self.cartao_acesso_id)

        return (
            f"Acesso {self.id}: {self.marcacao} on {self.date} at {self.time} "
            f"from cartao_id: {self.cartao_acesso_id}) (Catraca: {self.catraca})"
        )
