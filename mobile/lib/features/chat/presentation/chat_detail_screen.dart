import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../auth/data/auth_repository.dart';
import '../../reports/data/reports_repository.dart';
import '../data/chat_repository.dart';

class ChatDetailScreen extends ConsumerStatefulWidget {
  const ChatDetailScreen({
    super.key,
    required this.conversationId,
    this.initialConversation,
  });

  final int conversationId;
  final Map<String, dynamic>? initialConversation;

  @override
  ConsumerState<ChatDetailScreen> createState() => _ChatDetailScreenState();
}

class _ChatDetailScreenState extends ConsumerState<ChatDetailScreen> {
  static const TextStyle _bubbleTextStyle = TextStyle(
    fontSize: 14,
    height: 1.38,
  );
  static const TextStyle _bubbleTimeTextStyle = TextStyle(
    fontSize: 11,
    color: AppTheme.textSubtle,
  );
  static const double _bubbleHorizontalPadding = 24.0;
  static const double _inlineTimestampGap = 6.0;
  static const double _inlineTimestampSafetyPx = 3.0;

  final _messageCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _composerFocusNode = FocusNode();
  final ImagePicker _imagePicker = ImagePicker();

  List<Map<String, dynamic>> _messages = [];
  Map<String, dynamic>? _conversation;
  List<PlatformFile> _pickedFiles = [];

  bool _loading = true;
  bool _loadingMore = false;
  bool _sending = false;
  bool _reportSheetOpen = false;
  bool _reportSubmitInProgress = false;
  String? _error;

  int _currentPage = 1;
  int? _myUserId;

  Timer? _pollTimer;
  final Set<int> _downloadingAttachmentIds = <int>{};

  @override
  void initState() {
    super.initState();
    _conversation = widget.initialConversation == null
        ? null
        : Map<String, dynamic>.from(widget.initialConversation!);
    _bootstrap();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _messageCtrl.dispose();
    _scrollCtrl.dispose();
    _composerFocusNode.dispose();
    super.dispose();
  }

  void _focusComposer() {
    _scrollToBottom(animate: true);
    FocusScope.of(context).requestFocus(_composerFocusNode);
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final chatRepo = ref.read(chatRepositoryProvider);
      final authRepo = ref.read(authRepositoryProvider);

      final meFuture = authRepo.getMe();
      final conversationFuture = chatRepo.getConversation(
        widget.conversationId,
      );

      final me = await meFuture;
      final conversation = await conversationFuture;

      if (!mounted) {
        return;
      }

      _myUserId = (me['id'] as num?)?.toInt();
      _conversation = conversation;

      await _loadLatestMessages(showLoader: true);
      _startPolling();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (!mounted || _loading || _sending) {
        return;
      }
      _refreshSilently();
    });
  }

  Future<void> _refreshSilently() async {
    try {
      await _loadLatestMessages(showLoader: false, animateScroll: false);
    } catch (_) {}
  }

  List<Map<String, dynamic>> _toMapList(dynamic rawItems) {
    if (rawItems is! List) {
      return <Map<String, dynamic>>[];
    }
    return rawItems
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<void> _loadLatestMessages({
    required bool showLoader,
    bool animateScroll = true,
  }) async {
    if (showLoader) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final repo = ref.read(chatRepositoryProvider);

      final firstPage = await repo.listMessages(
        conversationId: widget.conversationId,
        page: 1,
        pageSize: 30,
        markRead: true,
      );

      final totalPagesRaw = (firstPage['total_pages'] as num?)?.toInt() ?? 0;

      List<Map<String, dynamic>> items = _toMapList(firstPage['items']);
      var currentPage = 1;

      if (totalPagesRaw > 1) {
        final latestPage = await repo.listMessages(
          conversationId: widget.conversationId,
          page: totalPagesRaw,
          pageSize: 30,
          markRead: false,
        );
        items = _toMapList(latestPage['items']);
        currentPage = totalPagesRaw;
      }

      if (!mounted) {
        return;
      }

      setState(() {
        _messages = items;
        _currentPage = currentPage;
        _loading = false;
        _loadingMore = false;
        _error = null;
      });

      _scrollToBottom(animate: animateScroll);
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _loadingMore = false;
        _error = e.toString();
      });
      rethrow;
    }
  }

  Future<void> _loadOlderMessages() async {
    if (_loading || _loadingMore || _currentPage <= 1) {
      return;
    }

    setState(() {
      _loadingMore = true;
    });

    try {
      final targetPage = _currentPage - 1;
      final data = await ref
          .read(chatRepositoryProvider)
          .listMessages(
            conversationId: widget.conversationId,
            page: targetPage,
            pageSize: 30,
            markRead: false,
          );
      final older = _toMapList(data['items']);

      if (!mounted) {
        return;
      }

      setState(() {
        _messages = <Map<String, dynamic>>[...older, ..._messages];
        _currentPage = targetPage;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadingMore = false;
      });
    }
  }

  Future<void> _refresh() async {
    await _loadLatestMessages(showLoader: false);
  }

  Future<void> _pickFiles() async {
    final picked = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: <String>['jpg', 'jpeg', 'png', 'webp', 'pdf'],
    );
    if (picked == null || picked.files.isEmpty) {
      return;
    }

    final currentPaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toSet();

    final nextFiles = picked.files.where((file) {
      final path = file.path;
      return path != null && path.isNotEmpty && !currentPaths.contains(path);
    }).toList();

    if (nextFiles.isEmpty) {
      return;
    }

    setState(() {
      _pickedFiles = <PlatformFile>[..._pickedFiles, ...nextFiles];
    });
  }

  Future<void> _pickFromGallery() async {
    final pickedImages = await _imagePicker.pickMultiImage(imageQuality: 88);
    if (pickedImages.isEmpty) {
      return;
    }

    final currentPaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toSet();

    final nextFiles = <PlatformFile>[];
    for (final image in pickedImages) {
      final path = image.path;
      if (path.isEmpty || currentPaths.contains(path)) {
        continue;
      }

      var size = 0;
      try {
        size = await File(path).length();
      } catch (_) {}

      nextFiles.add(PlatformFile(name: image.name, path: path, size: size));
    }

    if (nextFiles.isEmpty) {
      return;
    }

    setState(() {
      _pickedFiles = <PlatformFile>[..._pickedFiles, ...nextFiles];
    });
  }

  Future<void> _showAttachSheet() async {
    final l = S.of(context)!;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.28),
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: <Color>[
                    AppTheme.bgSurface,
                    AppTheme.bgMuted.withValues(alpha: 0.96),
                  ],
                ),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppTheme.border),
                boxShadow: <BoxShadow>[
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 40,
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppTheme.border,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      l.attachFile,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildAttachmentSourceAction(
                      icon: Icons.photo_library_outlined,
                      label: l.pickImages,
                      onTap: () async {
                        Navigator.of(sheetContext).pop();
                        await _pickFromGallery();
                      },
                    ),
                    const SizedBox(height: 8),
                    _buildAttachmentSourceAction(
                      icon: Icons.insert_drive_file_outlined,
                      label: l.pickFile,
                      onTap: () async {
                        Navigator.of(sheetContext).pop();
                        await _pickFiles();
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildAttachmentSourceAction({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return Material(
      color: AppTheme.white.withValues(alpha: 0.9),
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: AppTheme.bgMuted,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 18, color: AppTheme.accent),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Icon(
                Icons.chevron_right,
                size: 20,
                color: AppTheme.textSubtle,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<Map<String, String>?> _showMessageReportSheet() async {
    if (_reportSheetOpen) {
      return null;
    }

    _reportSheetOpen = true;

    final l = S.of(context)!;
    var selectedReason = 'spam';
    var reasonText = '';
    String? submitError;

    try {
      final payload = await showModalBottomSheet<Map<String, String>>(
        context: context,
        isScrollControlled: true,
        backgroundColor: Colors.transparent,
        barrierColor: Colors.black.withValues(alpha: 0.28),
        builder: (sheetContext) {
          return StatefulBuilder(
            builder: (sheetContext, setSheetState) {
              final reasons = <String, String>{
                'spam': l.spam,
                'scam': l.scam,
                'offensive': l.offensive,
                'other': l.other,
              };

              return SafeArea(
                top: false,
                child: Padding(
                  padding: EdgeInsets.fromLTRB(
                    10,
                    0,
                    10,
                    MediaQuery.of(sheetContext).viewInsets.bottom + 10,
                  ),
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: <Color>[
                          AppTheme.bgSurface,
                          AppTheme.bgMuted.withValues(alpha: 0.96),
                        ],
                      ),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.border),
                      boxShadow: <BoxShadow>[
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.08),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
                      child: SingleChildScrollView(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Center(
                              child: Container(
                                width: 40,
                                height: 4,
                                decoration: BoxDecoration(
                                  color: AppTheme.border,
                                  borderRadius: BorderRadius.circular(999),
                                ),
                              ),
                            ),
                            const SizedBox(height: 14),
                            Text(
                              l.reportMessage,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              l.reportReason,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.textSubtle,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: reasons.entries.map((entry) {
                                final isSelected = entry.key == selectedReason;
                                return ChoiceChip(
                                  label: Text(entry.value),
                                  selected: isSelected,
                                  backgroundColor: AppTheme.white,
                                  selectedColor: AppTheme.accent.withValues(
                                    alpha: 0.16,
                                  ),
                                  side: BorderSide(
                                    color: isSelected
                                        ? AppTheme.accent
                                        : AppTheme.border,
                                  ),
                                  labelStyle: TextStyle(
                                    color: AppTheme.textMain,
                                    fontWeight: isSelected
                                        ? FontWeight.w700
                                        : FontWeight.w600,
                                  ),
                                  onSelected: (selected) {
                                    if (!selected) {
                                      return;
                                    }
                                    setSheetState(() {
                                      selectedReason = entry.key;
                                    });
                                  },
                                );
                              }).toList(),
                            ),
                            const SizedBox(height: 10),
                            TextField(
                              maxLines: 3,
                              onChanged: (value) {
                                reasonText = value;
                                if (submitError != null) {
                                  setSheetState(() {
                                    submitError = null;
                                  });
                                }
                              },
                              decoration: InputDecoration(
                                labelText: l.description,
                              ),
                            ),
                            if (submitError != null) ...[
                              const SizedBox(height: 10),
                              Text(
                                submitError!,
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.statusError,
                                ),
                              ),
                            ],
                            const SizedBox(height: 14),
                            SizedBox(
                              height: 46,
                              child: ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.white,
                                  foregroundColor: AppTheme.textMain,
                                  side: const BorderSide(
                                    color: AppTheme.border,
                                  ),
                                  elevation: 0,
                                ),
                                onPressed: () {
                                  final details = reasonText.trim();
                                  if (details.isEmpty) {
                                    setSheetState(() {
                                      submitError = l.fieldRequired;
                                    });
                                    return;
                                  }

                                  Navigator.of(
                                    sheetContext,
                                  ).pop(<String, String>{
                                    'reason_code': selectedReason,
                                    'reason_text': details,
                                  });
                                },
                                child: Text(l.reportMessage),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              );
            },
          );
        },
      );

      return payload;
    } finally {
      _reportSheetOpen = false;
    }
  }

  Future<void> _showMessageActions(Map<String, dynamic> message) async {
    if (_reportSubmitInProgress || _reportSheetOpen) {
      return;
    }

    final messageId = (message['id'] as num?)?.toInt();
    if (messageId == null) {
      return;
    }

    final senderId = (message['sender_id'] as num?)?.toInt();
    if (_myUserId != null && senderId == _myUserId) {
      return;
    }

    final l = S.of(context)!;
    final reportPayload = await _showMessageReportSheet();
    if (!mounted || reportPayload == null) {
      return;
    }

    _reportSubmitInProgress = true;

    try {
      await ref
          .read(reportsRepositoryProvider)
          .createReport(
            targetType: 'message',
            targetId: messageId,
            reasonCode: reportPayload['reason_code'] ?? 'spam',
            reasonText: reportPayload['reason_text'] ?? '',
          );
    } on DioException catch (e) {
      if (!mounted) {
        _reportSubmitInProgress = false;
        return;
      }
      final data = e.response?.data;
      var message = l.errorOccurred;
      if (data is Map && data['detail'] is String) {
        message = data['detail'].toString();
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(message)));
      _reportSubmitInProgress = false;
      return;
    } catch (_) {
      if (!mounted) {
        _reportSubmitInProgress = false;
        return;
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(l.errorOccurred)));
      _reportSubmitInProgress = false;
      return;
    }

    if (!mounted) {
      _reportSubmitInProgress = false;
      return;
    }

    ScaffoldMessenger.maybeOf(
      context,
    )?.showSnackBar(SnackBar(content: Text(l.reportSubmitted)));
    _reportSubmitInProgress = false;
  }

  void _removePickedFile(int index) {
    setState(() {
      _pickedFiles = List<PlatformFile>.from(_pickedFiles)..removeAt(index);
    });
  }

  Future<void> _send() async {
    final l = S.of(context)!;
    final text = _messageCtrl.text.trim();
    final filePaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toList();

    if (text.isEmpty && filePaths.isEmpty) {
      return;
    }

    setState(() {
      _sending = true;
    });

    try {
      final repo = ref.read(chatRepositoryProvider);

      if (filePaths.isEmpty) {
        await repo.sendTextMessage(
          conversationId: widget.conversationId,
          textBody: text,
        );
      } else {
        await repo.sendMessageWithAttachments(
          conversationId: widget.conversationId,
          textBody: text.isEmpty ? null : text,
          filePaths: filePaths,
        );
      }

      _messageCtrl.clear();
      setState(() {
        _pickedFiles = <PlatformFile>[];
      });

      await _loadLatestMessages(showLoader: false);
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _sending = false;
        });
      }
    }
  }

  Future<void> _downloadAttachment(Map<String, dynamic> attachment) async {
    final l = S.of(context)!;
    final attachmentId = (attachment['id'] as num?)?.toInt();
    if (attachmentId == null) {
      return;
    }

    setState(() {
      _downloadingAttachmentIds.add(attachmentId);
    });

    try {
      final bytes = await ref
          .read(chatRepositoryProvider)
          .downloadAttachmentBytes(attachmentId);
      final originalName =
          attachment['original_name']?.toString() ?? 'attachment_$attachmentId';
      final safeName = _safeFileName(originalName);
      final targetPath = '${Directory.systemTemp.path}/$safeName';
      final file = File(targetPath);
      await file.writeAsBytes(bytes, flush: true);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.attachmentDownloaded(safeName, bytes.length))),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _downloadingAttachmentIds.remove(attachmentId);
        });
      }
    }
  }

  String _safeFileName(String value) {
    return value.replaceAll(RegExp(r'[<>:"/\\|?*]+'), '_');
  }

  String _friendlyError(Object error, S l) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }

        final errorNode = data['error'];
        if (errorNode is Map && errorNode['message'] != null) {
          return errorNode['message'].toString();
        }
      }

      if (error.message != null && error.message!.trim().isNotEmpty) {
        return error.message!;
      }
    }
    return l.errorOccurred;
  }

  void _scrollToBottom({required bool animate}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) {
        return;
      }

      final max = _scrollCtrl.position.maxScrollExtent;
      if (animate) {
        _scrollCtrl.animateTo(
          max,
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOut,
        );
      } else {
        _scrollCtrl.jumpTo(max);
      }
    });
  }

  String _messageTimeLabel(Map<String, dynamic> message) {
    final raw = message['sent_at']?.toString();
    if (raw == null || raw.isEmpty) {
      return '';
    }

    final date = DateTime.tryParse(raw);
    if (date == null) {
      return '';
    }

    final local = date.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  String _normalizeBubbleText(String text) {
    // Insert soft-break opportunities for very long tokens to prevent RenderFlex overflow.
    return text.replaceAllMapped(RegExp(r'\S{22,}'), (match) {
      final token = match.group(0)!;
      final buffer = StringBuffer();
      const chunk = 12;
      for (var i = 0; i < token.length; i += chunk) {
        final end = (i + chunk) < token.length ? (i + chunk) : token.length;
        if (i > 0) {
          buffer.write('\u200B');
        }
        buffer.write(token.substring(i, end));
      }
      return buffer.toString();
    });
  }

  double _measureSingleLineTextWidth(
    BuildContext context,
    String text,
    TextStyle style,
  ) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: Directionality.of(context),
      maxLines: 1,
    )..layout(minWidth: 0, maxWidth: double.infinity);
    return painter.width;
  }

  double _resolveBubbleMaxWidth({
    required BuildContext context,
    required String text,
    required String timeLabel,
    required bool hasAttachments,
  }) {
    final media = MediaQuery.of(context);
    final screenWidth = media.size.width;
    final baseMaxWidth = screenWidth >= 700
        ? 520.0
        : screenWidth *
              (media.orientation == Orientation.portrait ? 0.78 : 0.64);

    if (hasAttachments) {
      return baseMaxWidth;
    }

    const minBubbleWidth = 68.0;
    const minContentWidth = 44.0;

    final maxContentWidth = (baseMaxWidth - _bubbleHorizontalPadding)
        .clamp(minContentWidth, baseMaxWidth)
        .toDouble();
    final normalizedText = text.trimRight();
    final textLines = normalizedText.isEmpty
        ? const <String>['']
        : normalizedText.split('\n');

    var longestLineWidth = 0.0;
    for (final rawLine in textLines) {
      final line = rawLine.isEmpty ? ' ' : rawLine;
      final lineWidth = _measureSingleLineTextWidth(
        context,
        line,
        _bubbleTextStyle,
      );
      if (lineWidth > longestLineWidth) {
        longestLineWidth = lineWidth;
      }
    }

    final resolvedTimeLabel = timeLabel.isEmpty ? '00:00' : timeLabel;
    final timestampWidth = _measureSingleLineTextWidth(
      context,
      resolvedTimeLabel,
      _bubbleTimeTextStyle,
    );

    var widestContent = longestLineWidth > timestampWidth
        ? longestLineWidth
        : timestampWidth;

    if (textLines.length == 1) {
      final inlineCandidateWidth =
          longestLineWidth +
          _inlineTimestampGap +
          timestampWidth +
          _inlineTimestampSafetyPx;
      if (inlineCandidateWidth > widestContent) {
        widestContent = inlineCandidateWidth;
      }
    }

    final clampedContentWidth = widestContent
        .clamp(minContentWidth, maxContentWidth)
        .toDouble();

    return (clampedContentWidth + _bubbleHorizontalPadding)
        .clamp(minBubbleWidth, baseMaxWidth)
        .toDouble();
  }

  bool _canInlineTimestamp({
    required BuildContext context,
    required String text,
    required String timeLabel,
    required bool hasAttachments,
    required double bubbleMaxWidth,
  }) {
    if (hasAttachments) {
      return false;
    }

    final normalizedText = text.trim();
    if (normalizedText.isEmpty || normalizedText.contains('\n')) {
      return false;
    }

    if (RegExp(r'\S{20,}').hasMatch(normalizedText)) {
      return false;
    }

    const minContentWidth = 44.0;
    final maxContentWidth = (bubbleMaxWidth - _bubbleHorizontalPadding)
        .clamp(minContentWidth, bubbleMaxWidth)
        .toDouble();
    final resolvedTimeLabel = timeLabel.isEmpty ? '00:00' : timeLabel;

    final textWidth = _measureSingleLineTextWidth(
      context,
      normalizedText,
      _bubbleTextStyle,
    );
    final timeWidth = _measureSingleLineTextWidth(
      context,
      resolvedTimeLabel,
      _bubbleTimeTextStyle,
    );

    return textWidth + _inlineTimestampGap + timeWidth <=
        (maxContentWidth - _inlineTimestampSafetyPx);
  }

  Widget _buildTextWithPinnedTime({
    required String textBody,
    required String timeLabel,
  }) {
    final resolvedTimeLabel = timeLabel.isEmpty ? '00:00' : timeLabel;
    return Stack(
      children: [
        Text.rich(
          TextSpan(
            style: _bubbleTextStyle,
            children: [
              TextSpan(text: textBody),
              const WidgetSpan(
                alignment: PlaceholderAlignment.baseline,
                baseline: TextBaseline.alphabetic,
                child: SizedBox(width: _inlineTimestampGap),
              ),
              WidgetSpan(
                alignment: PlaceholderAlignment.baseline,
                baseline: TextBaseline.alphabetic,
                child: Opacity(
                  opacity: 0,
                  child: Text(resolvedTimeLabel, style: _bubbleTimeTextStyle),
                ),
              ),
            ],
          ),
        ),
        Positioned(
          right: 0,
          bottom: 0,
          child: Text(resolvedTimeLabel, style: _bubbleTimeTextStyle),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final listingId = (_conversation?['listing_id'] as num?)?.toInt();
    final listingTitle = _conversation?['listing_title']?.toString().trim();
    final hasListingTitle = listingTitle != null && listingTitle.isNotEmpty;
    final counterpartName = _conversation?['counterpart_name']
        ?.toString()
        .trim();
    final hasCounterpartName =
        counterpartName != null && counterpartName.isNotEmpty;
    final chatTitle = hasListingTitle
        ? listingTitle
        : listingId == null
        ? l.conversations
        : '${l.listingDetail} #$listingId';

    return Scaffold(
      appBar: AppBar(title: Text(chatTitle)),
      body: Column(
        children: [
          if (hasCounterpartName) _buildContactPanel(l, name: counterpartName),
          Expanded(child: _buildBody(l)),
          if (_pickedFiles.isNotEmpty) _buildPickedFilesStrip(),
          _buildComposer(l),
        ],
      ),
    );
  }

  Widget _buildContactPanel(S l, {required String name}) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.bgSurface,
        borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            name,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: _focusComposer,
            icon: const Icon(Icons.chat_bubble_outline),
            label: Text(l.writeAction),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _messages.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _messages.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppTheme.textSubtle,
            ),
            const SizedBox(height: 12),
            Text(l.errorOccurred),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _bootstrap, child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_messages.isEmpty) {
      return RefreshIndicator(
        onRefresh: _refresh,
        color: AppTheme.accent,
        child: ListView(
          children: [
            SizedBox(
              height: 300,
              child: Center(
                child: Text(
                  l.noMessages,
                  style: const TextStyle(color: AppTheme.textSubtle),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppTheme.accent,
      child: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification.metrics.pixels < 110) {
            _loadOlderMessages();
          }
          return false;
        },
        child: ListView.builder(
          controller: _scrollCtrl,
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 14),
          itemCount: _messages.length + (_loadingMore ? 1 : 0),
          itemBuilder: (context, index) {
            if (_loadingMore && index == 0) {
              return const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Center(
                  child: CircularProgressIndicator(
                    color: AppTheme.accent,
                    strokeWidth: 2,
                  ),
                ),
              );
            }

            final message = _messages[index - (_loadingMore ? 1 : 0)];
            return _buildMessageBubble(message);
          },
        ),
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> message) {
    final senderId = (message['sender_id'] as num?)?.toInt();
    final isMine = _myUserId != null && senderId == _myUserId;

    final textBody = message['text_body']?.toString();
    final hasTextBody = textBody != null && textBody.trim().isNotEmpty;
    final displayTextBody = hasTextBody ? _normalizeBubbleText(textBody) : '';
    final rawAttachments = message['attachments'];
    final attachments = _toMapList(rawAttachments);
    final hasAttachments = attachments.isNotEmpty;
    final hasAttachmentCaption = hasAttachments && hasTextBody;
    if (!hasTextBody && !hasAttachments) {
      return const SizedBox.shrink();
    }

    final timeLabel = _messageTimeLabel(message);
    final bubbleMaxWidth = _resolveBubbleMaxWidth(
      context: context,
      text: hasTextBody ? textBody : '',
      timeLabel: timeLabel,
      hasAttachments: hasAttachments,
    );
    final shouldInlineTimestamp =
        hasTextBody &&
        _canInlineTimestamp(
          context: context,
          text: displayTextBody,
          timeLabel: timeLabel,
          hasAttachments: hasAttachments,
          bubbleMaxWidth: bubbleMaxWidth,
        );
    final bubbleRadius = BorderRadius.only(
      topLeft: const Radius.circular(14),
      topRight: const Radius.circular(14),
      bottomLeft: Radius.circular(isMine ? 14 : 4),
      bottomRight: Radius.circular(isMine ? 4 : 14),
    );

    return Align(
      alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: GestureDetector(
          onLongPress: isMine || _reportSubmitInProgress || _reportSheetOpen
              ? null
              : () => _showMessageActions(message),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: bubbleMaxWidth),
            child: Container(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
              decoration: BoxDecoration(
                color: isMine
                    ? AppTheme.accent.withValues(alpha: 0.17)
                    : AppTheme.white,
                borderRadius: bubbleRadius,
                border: Border.all(color: AppTheme.border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (hasTextBody && shouldInlineTimestamp)
                    Row(
                      mainAxisSize: MainAxisSize.max,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Flexible(
                          child: Text(
                            displayTextBody,
                            maxLines: 1,
                            softWrap: false,
                            overflow: TextOverflow.ellipsis,
                            style: _bubbleTextStyle,
                          ),
                        ),
                        const SizedBox(width: _inlineTimestampGap),
                        Text(timeLabel, style: _bubbleTimeTextStyle),
                      ],
                    ),
                  if (hasTextBody && !shouldInlineTimestamp && !hasAttachments)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 0),
                      child: _buildTextWithPinnedTime(
                        textBody: displayTextBody,
                        timeLabel: timeLabel,
                      ),
                    ),
                  if (hasAttachments)
                    ...attachments.map(_buildAttachmentWidget),
                  if (hasAttachmentCaption)
                    _buildAttachmentCaptionAndTimeRow(
                      textBody: displayTextBody,
                      timeLabel: timeLabel,
                    ),
                  if (!shouldInlineTimestamp &&
                      !hasAttachmentCaption &&
                      !hasTextBody)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Align(
                        alignment: Alignment.centerRight,
                        child: Text(timeLabel, style: _bubbleTimeTextStyle),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAttachmentCaptionAndTimeRow({
    required String textBody,
    required String timeLabel,
  }) {
    final caption = textBody.trim();
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(child: Text(caption, style: _bubbleTextStyle)),
          const SizedBox(width: _inlineTimestampGap),
          Text(timeLabel, style: _bubbleTimeTextStyle),
        ],
      ),
    );
  }

  Widget _buildAttachmentWidget(Map<String, dynamic> attachment) {
    final mime = attachment['mime_type']?.toString() ?? '';
    final attachmentId = (attachment['id'] as num?)?.toInt();

    if (attachmentId == null) {
      return const SizedBox.shrink();
    }

    if (mime.startsWith('image/')) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: GestureDetector(
          onTap: () => _downloadAttachment(attachment),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: _InlineImageAttachment(attachmentId: attachmentId),
          ),
        ),
      );
    }

    final originalName = attachment['original_name']?.toString() ?? 'file';
    final isDownloading = _downloadingAttachmentIds.contains(attachmentId);

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: isDownloading ? null : () => _downloadAttachment(attachment),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isDownloading ? Icons.downloading : Icons.attach_file,
                  size: 18,
                  color: AppTheme.accent,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    originalName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.accent,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPickedFilesStrip() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: const BoxDecoration(
        color: AppTheme.bgSurface,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SizedBox(
        height: 40,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: _pickedFiles.length,
          separatorBuilder: (context, index) => const SizedBox(width: 8),
          itemBuilder: (context, index) {
            final file = _pickedFiles[index];
            final name = file.name;

            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.bgMuted,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.insert_drive_file_outlined, size: 16),
                  const SizedBox(width: 6),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 140),
                    child: Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => _removePickedFile(index),
                    child: const Icon(
                      Icons.close,
                      size: 16,
                      color: AppTheme.textSubtle,
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildComposer(S l) {
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: const BoxDecoration(
        color: AppTheme.bgSurface,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            SizedBox(
              width: 48,
              height: 48,
              child: IconButton(
                tooltip: l.attachFile,
                onPressed: _sending ? null : _showAttachSheet,
                icon: const Icon(Icons.attach_file),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _messageCtrl,
                focusNode: _composerFocusNode,
                enabled: !_sending,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.newline,
                decoration: InputDecoration(
                  hintText: l.typeMessage,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 48,
              height: 48,
              child: IconButton.filled(
                onPressed: _sending ? null : _send,
                icon: _sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InlineImageAttachment extends ConsumerStatefulWidget {
  const _InlineImageAttachment({required this.attachmentId});

  final int attachmentId;

  @override
  ConsumerState<_InlineImageAttachment> createState() =>
      _InlineImageAttachmentState();
}

class _InlineImageAttachmentState
    extends ConsumerState<_InlineImageAttachment> {
  late Future<Uint8List> _future;

  @override
  void initState() {
    super.initState();
    _future = ref
        .read(chatRepositoryProvider)
        .downloadAttachmentBytes(widget.attachmentId);
  }

  @override
  void didUpdateWidget(covariant _InlineImageAttachment oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.attachmentId != widget.attachmentId) {
      _future = ref
          .read(chatRepositoryProvider)
          .downloadAttachmentBytes(widget.attachmentId);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Container(
            height: 170,
            width: double.infinity,
            color: AppTheme.bgMuted,
            alignment: Alignment.center,
            child: const CircularProgressIndicator(
              color: AppTheme.accent,
              strokeWidth: 2,
            ),
          );
        }

        if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
          return Container(
            height: 120,
            width: double.infinity,
            color: AppTheme.bgMuted,
            alignment: Alignment.center,
            child: const Icon(
              Icons.broken_image_outlined,
              color: AppTheme.textSubtle,
              size: 28,
            ),
          );
        }

        return Image.memory(
          snapshot.data!,
          fit: BoxFit.cover,
          width: double.infinity,
          height: 190,
        );
      },
    );
  }
}
