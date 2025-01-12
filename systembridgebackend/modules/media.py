"""Media."""

# pylint: disable=import-error
import asyncio
from collections.abc import Awaitable, Callable
import datetime
from typing import Final

from winsdk.windows.foundation import EventRegistrationToken
import winsdk.windows.media.control as wmc

from systembridgemodels.modules.media import Media as MediaInfo
from systembridgeshared.base import Base

IDLE_UPDATE_INTERVAL: Final[int] = 20
PLAYING_UPDATE_INTERVAL: Final[int] = 5


class Media(Base):
    """Media."""

    def __init__(
        self,
        changed_callback: Callable[[str, MediaInfo], Awaitable[None]],
        update_media_info_interval: Callable[[int], None],
    ) -> None:
        """Initialise."""
        super().__init__()
        self._changed_callback = changed_callback

        self.sessions: None | (
            wmc.GlobalSystemMediaTransportControlsSessionManager
        ) = None
        self.current_session: None | (
            wmc.GlobalSystemMediaTransportControlsSession
        ) = None
        self.current_session_changed_handler_token: None | (
            EventRegistrationToken
        ) = None
        self.properties_changed_handler_token: EventRegistrationToken | None = None
        self.playback_info_changed_handler_token: None | (EventRegistrationToken) = None

        self.update_media_info_interval = update_media_info_interval

    def _current_session_changed_handler(
        self,
        _sender,
        _result,
    ) -> None:
        """Session changed handler."""
        self._logger.info("Session changed")
        if self._changed_callback is not None:
            asyncio.run(self.update_media_info())

    def _properties_changed_handler(
        self,
        _sender,
        _result,
    ) -> None:
        """Properties changed handler."""
        self._logger.info("Media properties changed")
        if self._changed_callback is not None:
            asyncio.run(self.update_media_info())

    def _playback_info_changed_handler(
        self,
        _sender,
        _result,
    ) -> None:
        """Playback info changed handler."""
        self._logger.info("Media properties changed")
        if self._changed_callback is not None:
            asyncio.run(self.update_media_info())

    async def _update_data(
        self,
        media_info: MediaInfo,
    ) -> None:
        """Update data."""
        self._logger.info("Updating media data")
        await self._changed_callback("media", media_info)

    async def update_media_info(self) -> None:
        """Update media info from the current session."""
        try:
            if (
                self.sessions is not None
                and self.current_session_changed_handler_token is not None
            ):
                self.sessions.remove_current_session_changed(
                    self.current_session_changed_handler_token
                )

            self.sessions = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            self.current_session_changed_handler_token = (
                self.sessions.add_current_session_changed(
                    self._current_session_changed_handler
                )
            )

            if self.current_session is not None:
                if self.properties_changed_handler_token is not None:
                    self.current_session.remove_media_properties_changed(
                        self.properties_changed_handler_token
                    )
                if self.playback_info_changed_handler_token is not None:
                    self.current_session.remove_playback_info_changed(
                        self.playback_info_changed_handler_token
                    )

            self.current_session = self.sessions.get_current_session()
            if self.current_session:
                self.properties_changed_handler_token = (
                    self.current_session.add_media_properties_changed(
                        self._properties_changed_handler
                    )
                )
                self.playback_info_changed_handler_token = (
                    self.current_session.add_playback_info_changed(
                        self._playback_info_changed_handler
                    )
                )
                media_info = MediaInfo(updated_at=datetime.datetime.now().timestamp())
                if info := self.current_session.get_playback_info():
                    media_info.status = info.playback_status.name
                    media_info.playback_rate = info.playback_rate
                    media_info.shuffle = info.is_shuffle_active
                    if info.auto_repeat_mode:
                        media_info.repeat = info.auto_repeat_mode.name
                    if info.playback_type:
                        media_info.type = info.playback_type.name
                    if info.controls:
                        media_info.is_fast_forward_enabled = (
                            info.controls.is_fast_forward_enabled
                        )
                        media_info.is_next_enabled = info.controls.is_next_enabled
                        media_info.is_pause_enabled = info.controls.is_pause_enabled
                        media_info.is_play_enabled = info.controls.is_play_enabled
                        media_info.is_previous_enabled = (
                            info.controls.is_previous_enabled
                        )
                        media_info.is_rewind_enabled = info.controls.is_rewind_enabled
                        media_info.is_stop_enabled = info.controls.is_stop_enabled

                if timeline := self.current_session.get_timeline_properties():
                    media_info.duration = timeline.end_time.total_seconds()
                    media_info.position = timeline.position.total_seconds()

                if (
                    properties
                    := await self.current_session.try_get_media_properties_async()
                ):
                    media_info.title = properties.title
                    media_info.subtitle = properties.subtitle
                    media_info.artist = properties.artist
                    media_info.album_artist = properties.album_artist
                    media_info.album_title = properties.album_title
                    media_info.track_number = properties.track_number

                media_info.updated_at = datetime.datetime.now().timestamp()

                await self._update_data(media_info)

                if media_info.status == "PLAYING":
                    self.update_media_info_interval(PLAYING_UPDATE_INTERVAL)
                else:
                    self.update_media_info_interval(IDLE_UPDATE_INTERVAL)
            else:
                await self._update_data(
                    MediaInfo(updated_at=datetime.datetime.now().timestamp())
                )
        except OSError as error:
            self._logger.error("Error updating media info: %s", error)
            await self._update_data(
                MediaInfo(updated_at=datetime.datetime.now().timestamp())
            )
