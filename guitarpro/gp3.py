# This file is part of alphaTab.
#
#  alphaTab is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  alphaTab is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with alphaTab.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

import copy

from guitarpro import base as gp

class GP3File(gp.GPFileBase):
    '''A reader for GuitarPro 3 files. 
    '''
    _tripletFeel = gp.TripletFeel.None_

    def __init__(self, *args, **kwargs):
        super(GP3File, self).__init__(*args, **kwargs)
        self.initVersions(["FICHIER GUITAR PRO v3.00"])
    
    def readSong(self):
        '''Reads the song

        :returns: The song read from the given stream using the specified factory
        '''
        if not self.readVersion():
            raise gp.GuitarProException("unsupported version '%s'" % self.version)
        
        song = gp.Song()

        self.readInfo(song)
        
        self._tripletFeel = (gp.TripletFeel.Eighth if self.readBool()
            else gp.TripletFeel.None_)
        
        self.readLyrics(song)
        
        self.readPageSetup(song)
        
        song.tempoName = ""
        song.tempo = self.readInt()
        song.hideTempo = False
       
        song.key = self.readInt()
        song.octave = 0
        
        channels = self.readMidiChannels()
        
        measureCount = self.readInt()
        trackCount = self.readInt()
        
        self.measureHeaders = self.readMeasureHeaders(song, measureCount)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)

        return song
    
    def readMeasures(self, song):
        tempo = gp.Tempo()
        tempo.value = song.tempo
        start = gp.Duration.QUARTER_TIME
        for header in song.measureHeaders:
            header.start = start
            for track in song.tracks:
                measure = gp.Measure(header)
                # header.tempo.copy(tempo)
                tempo = header.tempo
                track.addMeasure(measure)
                self.readMeasure(measure, track)
            
            # tempo.copy(header.tempo)
            header.tempo = tempo
            start += header.length()
    
    def readMeasure(self, measure, track):
        start = measure.start()
        beats = self.readInt()
        for beat in range(beats): 
            start += self.readBeat(start, measure, track, 0)
    
    def readBeat(self, start, measure, track, voiceIndex):
        flags = self.readByte()
        
        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]
        
        if flags & 0x40 != 0:
            beatType = self.readByte()
            voice.isEmpty = (beatType & 0x02) == 0
        
        duration = self.readDuration(flags)
        effect = gp.NoteEffect()
        if flags & 0x02 != 0:
            self.readChord(track.stringCount(), beat)
        
        if flags & 0x04 != 0:
            self.readText(beat)
        
        if flags & 0x08 != 0:
            self.readBeatEffects(beat, effect)
        
        if flags & 0x10 != 0:
            mixTableChange = self.readMixTableChange(measure)
            beat.effect.mixTableChange = mixTableChange
        
        stringFlags = self.readByte()
        for j in range(7):
            i = 6 - j
            if stringFlags & (1 << i) != 0 and (6 - i) < track.stringCount():
                # guitarString = track.strings[6 - i].clone(factory)
                guitarString = copy.deepcopy(track.strings[6 - i])
                # note = self.readNote(guitarString, track, effect.clone(factory))
                note = self.readNote(guitarString, track, copy.deepcopy(effect))
                voice.addNote(note)
            
            # duration.copy(voice.duration)
            voice.duration = copy.copy(duration)
        
        return duration.time() if not voice.isEmpty else 0
        
    def readNote(self, guitarString, track, effect):
        flags = self.readByte()
        note = gp.Note()
        note.string = guitarString.number
        note.effect = effect
        note.effect.accentuatedNote = (flags & 0x40) != 0
        note.effect.heavyAccentuatedNote = (flags & 0x02) != 0
        note.effect.ghostNote = (flags & 0x04) != 0
        if flags & 0x20 != 0:
            noteType = self.readByte()
            note.isTiedNote = noteType == 0x02
            note.effect.deadNote = noteType == 0x03
        
        if flags & 0x01 != 0:
            note.duration = self.readSignedByte()
            note.tuplet = self.readSignedByte()
        
        if flags & 0x10 != 0:
            note.velocity = ((gp.Velocities.MIN_VELOCITY + 
                (gp.Velocities.VELOCITY_INCREMENT * self.readSignedByte())) -
                gp.Velocities.VELOCITY_INCREMENT)
        
        if flags & 0x20 != 0:
            fret = self.readSignedByte()
            value = self.getTiedNoteValue(guitarString.number, track) if note.isTiedNote else fret
            note.value = value if value >= 0 and value < 100 else 0
        
        if flags & 0x80 != 0:
            note.effect.leftHandFinger = self.readSignedByte()
            note.effect.rightHandFinger = self.readSignedByte()
            note.effect.isFingering = True
        
        if flags & 0x08 != 0:
            self.readNoteEffects(note.effect)
        
        return note
    
    
    def readNoteEffects(self, noteEffect):
        flags1 = self.readByte()
        noteEffect.slide = (flags1 & 0x04) != 0
        noteEffect.hammer = (flags1 & 0x02) != 0
        noteEffect.letRing = (flags1 & 0x08) != 0

        if flags1 & 0x01 != 0:
            self.readBend(noteEffect)
        
        if flags1 & 0x10 != 0:
            self.readGrace(noteEffect)
    
    def readGrace(self, noteEffect):
        fret = self.readByte()
        dyn = self.readByte()
        transition = self.readSignedByte()
        duration = self.readByte()
        grace = gp.GraceEffect()
        
        grace.fret = fret
        grace.velocity = (gp.Velocities.MIN_VELOCITY + 
            gp.Velocities.VELOCITY_INCREMENT * dyn -
            gp.Velocities.VELOCITY_INCREMENT)
        grace.duration = duration
        grace.isDead = fret == 255
        grace.isOnBeat = False
        if transition == 0:
            grace.transition = gp.GraceEffectTransition.None_
        elif transition == 1:
            grace.transition = gp.GraceEffectTransition.Slide
        elif transition == 2:
            grace.transition = gp.GraceEffectTransition.Bend
        elif transition == 3:
            grace.transition = gp.GraceEffectTransition.Hammer
        
        noteEffect.grace = grace
    
    def readBend(self, noteEffect):
        bendEffect = gp.BendEffect()
        bendEffect.type = self.readSignedByte()
        bendEffect.value = self.readInt()
        pointCount = self.readInt()
        for i in range(pointCount):
            pointPosition = round(self.readInt() * gp.BendEffect.MAX_POSITION / gp.GPFileBase.BEND_POSITION)
            pointValue = round(self.readInt() * gp.BendEffect.SEMITONE_LENGTH / gp.GPFileBase.BEND_SEMITONE)
            vibrato = self.readBool()
            bendEffect.points.append(gp.BendPoint(pointPosition, pointValue, vibrato))

        if pointCount > 0:
            noteEffect.bend = bendEffect
    
    def readMixTableChange(self, measure):
        tableChange = gp.MixTableChange()
        tableChange.instrument.value = self.readSignedByte()
        tableChange.volume.value = self.readSignedByte()
        tableChange.balance.value = self.readSignedByte()
        tableChange.chorus.value = self.readSignedByte()
        tableChange.reverb.value = self.readSignedByte()
        tableChange.phaser.value = self.readSignedByte()
        tableChange.tremolo.value = self.readSignedByte()
        tableChange.tempoName = ""
        tableChange.tempo.value = self.readInt()
        
        if tableChange.instrument.value < 0:
            tableChange.instrument = None
        
        if tableChange.volume.value >= 0:
            tableChange.volume.duration = self.readSignedByte()
        else:
            tableChange.volume = None
        if tableChange.balance.value >= 0:
            tableChange.balance.duration = self.readSignedByte()
        else:
            tableChange.balance = None
        if tableChange.chorus.value >= 0:
            tableChange.chorus.duration = self.readSignedByte()
        else:
            tableChange.chorus = None
        if tableChange.reverb.value >= 0:
            tableChange.reverb.duration = self.readSignedByte()
        else:
            tableChange.reverb = None
        if tableChange.phaser.value >= 0:
            tableChange.phaser.duration = self.readSignedByte()
        else:
            tableChange.phaser = None
        if tableChange.tremolo.value >= 0:
            tableChange.tremolo.duration = self.readSignedByte()
        else:
            tableChange.tremolo = None
        if tableChange.tempo.value >= 0:
            tableChange.tempo.duration = self.readSignedByte()
            measure.tempo().value = tableChange.tempo.value
            tableChange.hideTempo = False
        else:
            tableChange.tempo = None
        return tableChange
    
    def readBeatEffects(self, beat, effect):
        flags1 = self.readByte()
        beat.effect.fadeIn = (flags1 & 0x10) != 0
        beat.effect.vibrato = (flags1 & 0x02) != 0 or beat.effect.vibrato
        if flags1 & 0x20 != 0:
            slapEffect = self.readByte()
            if slapEffect == 0:
                self.readTremoloBar(beat.effect)
            else:
                beat.effect.tapping = slapEffect == 1
                beat.effect.slapping = slapEffect == 2
                beat.effect.popping = slapEffect == 3
                self.readInt()
        if flags1 & 0x40 != 0:
            strokeUp = self.readSignedByte()
            strokeDown = self.readSignedByte()
            if strokeUp > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.Up
                beat.effect.stroke.value = self.toStrokeValue(strokeUp)
            else:
                if strokeDown > 0:
                    beat.effect.stroke.direction = gp.BeatStrokeDirection.Down
                    beat.effect.stroke.value = self.toStrokeValue(strokeDown)
        if flags1 & 0x04 != 0:
            harmonic = gp.HarmonicEffect()
            harmonic.type = gp.HarmonicType.Natural
            effect.harmonic = harmonic
        
        if (flags1 & 0x08) != 0:
            harmonic = gp.HarmonicEffect()
            harmonic.type = gp.HarmonicType.Artificial
            harmonic.self = 0
            effect.harmonic = harmonic
    
    def readTremoloBar(self, effect):
        barEffect = gp.BendEffect()
        barEffect.type = self.readSignedByte()
        barEffect.value = self.readInt()
        
        barEffect.points.append(gp.BendPoint(0, 0, False))
        barEffect.points.append(gp.BendPoint(round(gp.BendEffect.MAX_POSITION / 2), 
            round(barEffect.value / (gp.GPFileBase.BEND_SEMITONE * 2)), 
            False))
        barEffect.points.append(gp.BendPoint(gp.BendEffect.MAX_POSITION, 0, False))
        
        effect.tremoloBar = barEffect
    
    def readText(self, beat):
        text = gp.BeatText()
        text.value = self.readIntSizeCheckByteString()
        beat.setText(text)
    
    def readChord(self, stringCount, beat):
        # chord = factory.newChord(stringCount)
        chord = gp.Chord(stringCount)
        if (self.readByte() & 0x01) == 0:
            chord.name = self.readIntSizeCheckByteString()
            chord.firstFret = self.readInt()
            if chord.firstFret != 0:
                for i in range(6):
                    fret = self.readInt()
                    if i < len(chord.strings):
                        chord.strings[i] = fret
        else:
            self.skip(25)
            chord.name = self.readByteSizeString(34)
            chord.firstFret = self.readInt()
            for i in range(6):
                fret = self.readInt()
                if i < len(chord.strings):
                    chord.strings[i] = fret
            self.skip(36)
        if chord.noteCount() > 0:
            beat.setChord(chord)
    
    def readDuration(self, flags):
        duration = gp.Duration()
        duration.value = round(2 ** (self.readSignedByte() + 4)) / 4
        duration.isDotted = (flags & 0x01) != 0
        if (flags & 0x20) != 0:
            iTuplet = self.readInt()
            if iTuplet == 3:
                duration.tuplet.enters = 3
                duration.tuplet.times = 2
            elif iTuplet == 5:
                duration.tuplet.enters = 5
                duration.tuplet.times = 4
            elif iTuplet == 6:
                duration.tuplet.enters = 6
                duration.tuplet.times = 4
            elif iTuplet == 7:
                duration.tuplet.enters = 7
                duration.tuplet.times = 4
            elif iTuplet == 9:
                duration.tuplet.enters = 9
                duration.tuplet.times = 8
            elif iTuplet == 10:
                duration.tuplet.enters = 10
                duration.tuplet.times = 8
            elif iTuplet == 11:
                duration.tuplet.enters = 11
                duration.tuplet.times = 8
            elif iTuplet == 12:
                duration.tuplet.enters = 12
                duration.tuplet.times = 8
        return duration
    
    def getBeat(self, measure, start):
        for beat in measure.beats:
            if beat.start == start:
                return beat
        newBeat = gp.Beat()
        newBeat.start = start
        measure.addBeat(newBeat)
        return newBeat
    
    def readTracks(self, song, trackCount, channels):
        for i in range(1, trackCount + 1):
            song.addTrack(self.readTrack(i, channels))
        
    def readTrack(self, number, channels):
        flags = self.readByte()
        track = gp.Track()
        track.isPercussionTrack = (flags & 0x1) != 0
        track.is12StringedGuitarTrack = (flags & 0x02) != 0
        track.isBanjoTrack = (flags & 0x04) != 0
        track.number = number
        track.name = self.readByteSizeString(40)
        stringCount = self.readInt()
        for i in range(7):
            iTuning = self.readInt()
            if stringCount > i:
                oString = gp.GuitarString()
                oString.number = i + 1
                oString.value = iTuning
                track.strings.append(oString)
        track.port = self.readInt()
        self.readChannel(track.channel, channels)
        if track.channel.channel == 9:
            track.isPercussionTrack = True
        track.fretCount = self.readInt()
        track.offset = self.readInt()
        track.color = self.readColor()
        
        return track
    
    def readChannel(self, midiChannel, channels):
        index = self.readInt() - 1
        effectChannel = self.readInt() - 1
        if 0 <= index < len(channels):
            # channels[index].copy(midiChannel)
            midiChannel = channels[index]
            if midiChannel.instrument() < 0:
                midiChannel.instrument(0)
            if not midiChannel.isPercussionChannel():
                midiChannel.effectChannel = effectChannel
    
    def readMeasureHeaders(self, song, measureCount):
        timeSignature = gp.TimeSignature()
        for i in range(measureCount):
            song.addMeasureHeader(self.readMeasureHeader(i, timeSignature, song))
    
    def readMeasureHeader(self, i, timeSignature, song):
        flags = self.readByte()
        
        header = gp.MeasureHeader()
        header.number = i + 1
        header.start = 0
        header.tempo.value = song.tempo
        header.tripletFeel = self._tripletFeel
        
        if (flags & 0x01) != 0:
            timeSignature.numerator = self.readSignedByte()
        if (flags & 0x02) != 0:
            timeSignature.denominator.value = self.readSignedByte()
        
        header.isRepeatOpen = ((flags & 0x04) != 0)
        
        # timeSignature.copy(header.timeSignature)
        header.timeSignature = timeSignature
        
        if (flags & 0x08) != 0:
            header.repeatClose = (self.readSignedByte() - 1)
        
        if (flags & 0x10) != 0:
            header.repeatAlternative = self.parseRepeatAlternative(song, header.number, self.readByte())
        
        if (flags & 0x20) != 0:
            header.marker = self.readMarker(header)
        
        if (flags & 0x40) != 0:
            header.keySignature = self.toKeySignature(self.readSignedByte())
            header.keySignatureType = self.readSignedByte()
        
        elif header.number > 1:
            header.keySignature = song.measureHeaders[i - 1].keySignature
            header.keySignatureType = song.measureHeaders[i - 1].keySignatureType

        header.hasDoubleBar = (flags & 0x80) != 0
       
        return header
    
    def parseRepeatAlternative(self, song, measure, value):
        repeatAlternative = 0
        existentAlternatives = 0
        for header in song.measureHeaders:
            if header.number == measure:
                break
            if header.isRepeatOpen:
                existentAlternatives = 0
            existentAlternatives |= header.repeatAlternative
        for i in range(8):
            if value > i and (existentAlternatives & (1 << i)) == 0:
                repeatAlternative |= (1 << i)
        return repeatAlternative
    
    def readMarker(self, header):
        marker = gp.Marker()
        marker.measureHeader = header
        marker.title = self.readIntSizeCheckByteString()
        marker.color = self.readColor()
        return marker
    
    def readColor(self):
        r = self.readByte()
        g = self.readByte()
        b = self.readByte()
        self.skip(1)
        return gp.Color.fromRgb(r, g, b)
    
    def readMidiChannels(self):
        channels = []
        for i in range(64):
            newChannel = gp.MidiChannel()
            newChannel.channel = i
            newChannel.effectChannel = i
            newChannel.instrument(self.readInt())

            newChannel.volume = self.toChannelShort(self.readSignedByte())
            newChannel.balance = self.toChannelShort(self.readSignedByte())
            newChannel.chorus = self.toChannelShort(self.readSignedByte())
            newChannel.reverb = self.toChannelShort(self.readSignedByte())
            newChannel.phaser = self.toChannelShort(self.readSignedByte())
            newChannel.tremolo = self.toChannelShort(self.readSignedByte())
            channels.append(newChannel)
            # Backward compatibility with version 3.0
            self.skip(2)
        
        return channels
    
    def readPageSetup(self, song):
        song.pageSetup = gp.PageSetup()
    
    def readLyrics(self, song):
        song.lyrics = gp.Lyrics()
    
    def readInfo(self, song):
        song.title = self.readIntSizeCheckByteString()
        song.subtitle = self.readIntSizeCheckByteString()
        song.artist = self.readIntSizeCheckByteString()
        song.album = self.readIntSizeCheckByteString()
        song.words = self.readIntSizeCheckByteString()
        song.music = song.words
        song.copyright = self.readIntSizeCheckByteString()
        song.tab = self.readIntSizeCheckByteString()
        song.instructions = self.readIntSizeCheckByteString()
        
        iNotes = self.readInt()
        song.notice = ""
        for i in range(iNotes):
            song.notice += self.readIntSizeCheckByteString() + "\n"
    
    def toKeySignature(self, p):
        return 7 + abs(p) if p < 0 else p
    
    def toStrokeValue(self, value):
        if value == 1:
            return gp.Duration.SIXTY_FOURTH
        elif value == 2:
            return gp.Duration.SIXTY_FOURTH
        elif value == 3:
            return gp.Duration.THIRTY_SECOND
        elif value == 4:
            return gp.Duration.SIXTEENTH
        elif value == 5:
            return gp.Duration.EIGHTH
        elif value == 6:
            return gp.Duration.QUARTER
        else:
            return gp.Duration.SIXTY_FOURTH
