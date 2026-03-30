import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/theme.dart';
import '../data/categories_repository.dart';
import '../data/listings_repository.dart';

class ListingFormScreen extends ConsumerStatefulWidget {
  const ListingFormScreen({super.key, this.listingId, this.initialListing});

  final int? listingId;
  final Map<String, dynamic>? initialListing;

  bool get isEdit => listingId != null;

  @override
  ConsumerState<ListingFormScreen> createState() => _ListingFormScreenState();
}

class _ListingFormScreenState extends ConsumerState<ListingFormScreen> {
  final _formKey = GlobalKey<FormState>();

  final _titleCtrl = TextEditingController();
  final _descriptionCtrl = TextEditingController();
  final _priceCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();

  final Map<String, TextEditingController> _dynamicTextControllers = {};
  final Map<String, dynamic> _dynamicDiscreteValues = {};

  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _dynamicDefs = [];
  List<Map<String, dynamic>> _existingMedia = [];
  final List<XFile> _newMedia = [];

  int? _categoryId;
  String _transactionType = 'sale';
  String _currency = 'KGS';

  double? _latitude;
  double? _longitude;
  String? _mapAddressLabel;

  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descriptionCtrl.dispose();
    _priceCtrl.dispose();
    _cityCtrl.dispose();
    _addressCtrl.dispose();
    for (final controller in _dynamicTextControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final categories = await ref
          .read(categoriesRepositoryProvider)
          .getCategories(activeOnly: true);
      _categories = categories
          .map((raw) => Map<String, dynamic>.from(raw as Map))
          .toList();

      if (widget.isEdit) {
        final repo = ref.read(listingsRepositoryProvider);
        final listing =
            widget.initialListing ??
            await _loadMyListingForEdit(repo, widget.listingId!);
        if (listing == null) {
          throw Exception('Listing not found');
        }
        _applyListing(listing);
        final media = await repo.getMyListingMedia(widget.listingId!);
        _existingMedia = media
            .map((raw) => Map<String, dynamic>.from(raw as Map))
            .toList();
      } else if (_categories.isNotEmpty) {
        _categoryId = _categories.first['id'] as int;
        _syncDynamicSchema(initialValues: const {});
      }

      setState(() {
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  Future<Map<String, dynamic>?> _loadMyListingForEdit(
    ListingsRepository repo,
    int listingId,
  ) async {
    var page = 1;

    while (true) {
      final data = await repo.getMyListings(page: page, pageSize: 100);
      final items = (data['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();

      for (final item in items) {
        if (item['id'] == listingId) {
          return item;
        }
      }

      final totalPages = (data['total_pages'] as int?) ?? 1;
      if (page >= totalPages || items.isEmpty) {
        return null;
      }

      page += 1;
    }
  }

  void _applyListing(Map<String, dynamic> listing) {
    _titleCtrl.text = listing['title'] as String? ?? '';
    _descriptionCtrl.text = listing['description'] as String? ?? '';
    _priceCtrl.text = listing['price']?.toString() ?? '';
    _cityCtrl.text = listing['city'] as String? ?? '';
    _addressCtrl.text = listing['address_line'] as String? ?? '';

    _categoryId = listing['category_id'] as int?;
    _transactionType = listing['transaction_type'] as String? ?? 'sale';
    _currency = (listing['currency'] as String? ?? 'KGS').toUpperCase();

    _latitude = double.tryParse(listing['latitude']?.toString() ?? '');
    _longitude = double.tryParse(listing['longitude']?.toString() ?? '');
    _mapAddressLabel = listing['map_address_label'] as String?;

    final dynamicAttrs = Map<String, dynamic>.from(
      (listing['dynamic_attributes'] as Map?)?.cast<String, dynamic>() ??
          <String, dynamic>{},
    );
    _syncDynamicSchema(initialValues: dynamicAttrs);
  }

  Map<String, dynamic>? _findCategoryById(int? id) {
    if (id == null) return null;
    for (final category in _categories) {
      if (category['id'] == id) {
        return category;
      }
    }
    return null;
  }

  void _syncDynamicSchema({required Map<String, dynamic> initialValues}) {
    final category = _findCategoryById(_categoryId);
    final rawSchema =
        (category?['attributes_schema'] as List<dynamic>?) ?? const [];
    final nextDefs = rawSchema
        .whereType<Map>()
        .map((raw) => Map<String, dynamic>.from(raw))
        .toList();

    final preserved = <String, dynamic>{};
    preserved.addAll(initialValues);

    for (final entry in _dynamicTextControllers.entries) {
      preserved[entry.key] = entry.value.text;
    }
    for (final entry in _dynamicDiscreteValues.entries) {
      preserved[entry.key] = entry.value;
    }

    final nextKeys = nextDefs
        .map((def) => def['key']?.toString() ?? '')
        .where((key) => key.isNotEmpty)
        .toSet();

    final staleControllerKeys = _dynamicTextControllers.keys
        .where((key) => !nextKeys.contains(key))
        .toList();
    for (final key in staleControllerKeys) {
      _dynamicTextControllers[key]?.dispose();
      _dynamicTextControllers.remove(key);
    }

    final staleDiscreteKeys = _dynamicDiscreteValues.keys
        .where((key) => !nextKeys.contains(key))
        .toList();
    for (final key in staleDiscreteKeys) {
      _dynamicDiscreteValues.remove(key);
    }

    for (final def in nextDefs) {
      final key = def['key']?.toString();
      if (key == null || key.isEmpty) continue;

      final valueType = def['value_type']?.toString() ?? 'string';
      final options =
          (def['options'] as List?)?.map((item) => item.toString()).toList() ??
          const <String>[];
      final preservedValue = preserved[key];

      if (valueType == 'boolean' || options.isNotEmpty) {
        if (preservedValue != null) {
          _dynamicDiscreteValues[key] = preservedValue;
        }
      } else {
        final controller = _dynamicTextControllers.putIfAbsent(
          key,
          TextEditingController.new,
        );
        controller.text = preservedValue?.toString() ?? '';
      }
    }

    _dynamicDefs = nextDefs;
  }

  String _transactionLabel(String value, S l) {
    switch (value) {
      case 'sale':
        return l.sale;
      case 'rent_long':
        return l.rentLong;
      case 'rent_daily':
        return l.rentDaily;
      default:
        return value;
    }
  }

  Future<void> _pickImages() async {
    final picker = ImagePicker();
    final picked = await picker.pickMultiImage(imageQuality: 86);
    if (picked.isEmpty) return;
    setState(() {
      _newMedia.addAll(picked);
    });
  }

  Future<void> _removeExistingMedia(int mediaId) async {
    final l = S.of(context)!;
    final repo = ref.read(listingsRepositoryProvider);
    try {
      await repo.deleteListingMedia(mediaId);
      setState(() {
        _existingMedia.removeWhere((media) => media['id'] == mediaId);
      });
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    }
  }

  Future<void> _pickMapLocation() async {
    final picked = await showModalBottomSheet<_MapSelection>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) {
        return _MapPickerSheet(
          initialLatitude: _latitude,
          initialLongitude: _longitude,
          initialAddressLabel: _mapAddressLabel,
        );
      },
    );

    if (picked == null) return;

    setState(() {
      _latitude = picked.latitude;
      _longitude = picked.longitude;
      _mapAddressLabel = picked.addressLabel;
    });
  }

  Map<String, dynamic>? _collectDynamicPayload() {
    final l = S.of(context)!;
    final result = <String, dynamic>{};

    for (final def in _dynamicDefs) {
      final key = def['key']?.toString();
      if (key == null || key.isEmpty) continue;

      final label = (def['label']?.toString().trim().isNotEmpty ?? false)
          ? def['label'].toString()
          : key;
      final valueType = def['value_type']?.toString() ?? 'string';
      final required = def['required'] == true;
      final options =
          (def['options'] as List?)?.map((item) => item.toString()).toList() ??
          const <String>[];

      if (valueType == 'boolean') {
        final value = _dynamicDiscreteValues[key];
        if (required && value == null) {
          _showValidationMessage('$label: ${l.fieldRequired}');
          return null;
        }
        if (value != null) result[key] = value == true;
        continue;
      }

      if (options.isNotEmpty) {
        final value = _dynamicDiscreteValues[key]?.toString().trim() ?? '';
        if (required && value.isEmpty) {
          _showValidationMessage('$label: ${l.fieldRequired}');
          return null;
        }
        if (value.isNotEmpty) result[key] = value;
        continue;
      }

      final raw = _dynamicTextControllers[key]?.text.trim() ?? '';
      if (raw.isEmpty) {
        if (required) {
          _showValidationMessage('$label: ${l.fieldRequired}');
          return null;
        }
        continue;
      }

      if (valueType == 'integer') {
        final parsed = int.tryParse(raw);
        if (parsed == null) {
          _showValidationMessage('$label: ${l.invalidNumber}');
          return null;
        }
        result[key] = parsed;
        continue;
      }

      if (valueType == 'number') {
        final parsed = double.tryParse(raw.replaceAll(',', '.'));
        if (parsed == null) {
          _showValidationMessage('$label: ${l.invalidNumber}');
          return null;
        }
        result[key] = parsed;
        continue;
      }

      result[key] = raw;
    }

    return result.isEmpty ? null : result;
  }

  void _showValidationMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _save() async {
    final l = S.of(context)!;

    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }

    if (_categoryId == null) {
      _showValidationMessage(l.selectCategory);
      return;
    }

    if (_latitude == null || _longitude == null) {
      _showValidationMessage(l.setLocationFirst);
      return;
    }

    final price = double.tryParse(_priceCtrl.text.trim().replaceAll(',', '.'));
    if (price == null || price <= 0) {
      _showValidationMessage(l.invalidNumber);
      return;
    }

    final dynamicPayload = _collectDynamicPayload();
    if (_dynamicDefs.isNotEmpty && dynamicPayload == null) {
      final hasRequired = _dynamicDefs.any((def) => def['required'] == true);
      if (hasRequired) {
        return;
      }
    }

    final payload = <String, dynamic>{
      'category_id': _categoryId,
      'transaction_type': _transactionType,
      'title': _titleCtrl.text.trim(),
      'description': _descriptionCtrl.text.trim(),
      'price': price,
      'currency': _currency,
      'city': _cityCtrl.text.trim(),
      'address_line': _addressCtrl.text.trim().isEmpty
          ? null
          : _addressCtrl.text.trim(),
      'latitude': _latitude,
      'longitude': _longitude,
      'map_address_label': _mapAddressLabel,
      'dynamic_attributes': dynamicPayload,
    };

    setState(() {
      _saving = true;
    });

    final repo = ref.read(listingsRepositoryProvider);

    try {
      int listingId;

      if (widget.isEdit) {
        listingId = widget.listingId!;
        await repo.updateListing(listingId, payload);
      } else {
        final created = await repo.createListing(payload);
        listingId = created['id'] as int;
      }

      if (_newMedia.isNotEmpty) {
        await repo.uploadListingMedia(
          listingId: listingId,
          filePaths: _newMedia.map((file) => file.path).toList(),
        );
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(widget.isEdit ? l.listingUpdated : l.listingCreated),
        ),
      );

      if (widget.isEdit) {
        context.pop(true);
      } else {
        context.go('/my-listings');
      }
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.errorOccurred)));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  AppBar _buildAppBar(S l) {
    return AppBar(
      title: Text(widget.isEdit ? l.editListing : l.createListing),
      automaticallyImplyLeading: widget.isEdit,
      leading: widget.isEdit
          ? null
          : IconButton(
              icon: const Icon(Icons.arrow_back),
              onPressed: () {
                if (Navigator.of(context).canPop()) {
                  context.pop();
                } else {
                  context.go('/my-listings');
                }
              },
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    if (_loading) {
      return Scaffold(
        appBar: _buildAppBar(l),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: _buildAppBar(l),
        body: Center(
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
        ),
      );
    }

    return Scaffold(
      appBar: _buildAppBar(l),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: _titleCtrl,
                  decoration: InputDecoration(labelText: l.title),
                  textInputAction: TextInputAction.next,
                  validator: (value) {
                    final trimmed = value?.trim() ?? '';
                    if (trimmed.isEmpty) return l.fieldRequired;
                    if (trimmed.length < 3) return l.titleTooShort;
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _descriptionCtrl,
                  minLines: 4,
                  maxLines: 7,
                  decoration: InputDecoration(labelText: l.description),
                  validator: (value) {
                    final trimmed = value?.trim() ?? '';
                    if (trimmed.isEmpty) return l.fieldRequired;
                    if (trimmed.length < 10) return l.descriptionTooShort;
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<int>(
                  initialValue: _categoryId,
                  decoration: InputDecoration(labelText: l.category),
                  items: _categories
                      .map(
                        (category) => DropdownMenuItem<int>(
                          value: category['id'] as int,
                          child: Text(category['name'] as String? ?? ''),
                        ),
                      )
                      .toList(),
                  onChanged: (value) {
                    if (value == null) {
                      return;
                    }
                    setState(() {
                      _categoryId = value;
                      _syncDynamicSchema(initialValues: const {});
                    });
                  },
                  validator: (value) => value == null ? l.selectCategory : null,
                ),
                const SizedBox(height: 12),
                Text(
                  l.transactionType,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: ['sale', 'rent_long', 'rent_daily'].map((value) {
                    final selected = _transactionType == value;
                    return ChoiceChip(
                      label: Text(_transactionLabel(value, l)),
                      selected: selected,
                      selectedColor: AppTheme.accent,
                      backgroundColor: AppTheme.bgSurface,
                      side: BorderSide(
                        color: selected ? AppTheme.accent : AppTheme.border,
                      ),
                      labelStyle: TextStyle(
                        color: selected ? Colors.white : AppTheme.textSubtle,
                        fontWeight: FontWeight.w600,
                      ),
                      checkmarkColor: Colors.white,
                      onSelected: (_) {
                        setState(() {
                          _transactionType = value;
                        });
                      },
                    );
                  }).toList(),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _priceCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: InputDecoration(labelText: l.price),
                        validator: (value) {
                          final parsed = double.tryParse(
                            (value ?? '').trim().replaceAll(',', '.'),
                          );
                          if (parsed == null || parsed <= 0) {
                            return l.invalidNumber;
                          }
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    SizedBox(
                      width: 110,
                      child: DropdownButtonFormField<String>(
                        initialValue: _currency,
                        decoration: InputDecoration(labelText: l.currency),
                        items: const [
                          DropdownMenuItem(value: 'KGS', child: Text('KGS')),
                          DropdownMenuItem(value: 'USD', child: Text('USD')),
                        ],
                        onChanged: (value) {
                          if (value == null) {
                            return;
                          }
                          setState(() {
                            _currency = value;
                          });
                        },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _cityCtrl,
                  decoration: InputDecoration(labelText: l.city),
                  validator: (value) {
                    final trimmed = value?.trim() ?? '';
                    if (trimmed.isEmpty) return l.fieldRequired;
                    if (trimmed.length < 2) return l.cityTooShort;
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _addressCtrl,
                  decoration: InputDecoration(labelText: l.address),
                ),
                const SizedBox(height: 14),
                Text(
                  l.setLocation,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                if (_latitude != null && _longitude != null)
                  SizedBox(
                    height: 170,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                      child: FlutterMap(
                        options: MapOptions(
                          initialCenter: LatLng(_latitude!, _longitude!),
                          initialZoom: 15,
                          interactionOptions: const InteractionOptions(
                            flags: InteractiveFlag.none,
                          ),
                        ),
                        children: [
                          TileLayer(
                            urlTemplate:
                                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                            userAgentPackageName: 'kg.demo.km_marketplace',
                          ),
                          MarkerLayer(
                            markers: [
                              Marker(
                                point: LatLng(_latitude!, _longitude!),
                                width: 42,
                                height: 42,
                                child: const Icon(
                                  Icons.location_pin,
                                  color: AppTheme.accent,
                                  size: 42,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.bgMuted,
                      borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Text(
                      l.setLocationFirst,
                      style: const TextStyle(color: AppTheme.textSubtle),
                    ),
                  ),
                const SizedBox(height: 8),
                if ((_mapAddressLabel ?? '').trim().isNotEmpty)
                  Text(
                    _mapAddressLabel!,
                    style: const TextStyle(
                      color: AppTheme.textSubtle,
                      fontSize: 12,
                    ),
                  ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _pickMapLocation,
                  icon: const Icon(Icons.map_outlined),
                  label: Text(l.setLocation),
                ),
                const SizedBox(height: 14),
                Text(
                  l.listingPhotos,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                if (_existingMedia.isNotEmpty || _newMedia.isNotEmpty)
                  SizedBox(
                    height: 120,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        ..._existingMedia.map((media) {
                          final mediaId = media['id'] as int;
                          final imageUrl = ref
                              .read(listingsRepositoryProvider)
                              .absoluteUrl(
                                media['thumbnail_url']?.toString() ??
                                    media['file_url']?.toString() ??
                                    '',
                              );
                          return Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: Stack(
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(10),
                                  child: CachedNetworkImage(
                                    imageUrl: imageUrl,
                                    width: 120,
                                    height: 120,
                                    fit: BoxFit.cover,
                                  ),
                                ),
                                Positioned(
                                  right: 4,
                                  top: 4,
                                  child: InkWell(
                                    onTap: () => _removeExistingMedia(mediaId),
                                    borderRadius: BorderRadius.circular(16),
                                    child: Container(
                                      padding: const EdgeInsets.all(4),
                                      decoration: BoxDecoration(
                                        color: Colors.black.withValues(
                                          alpha: 0.6,
                                        ),
                                        shape: BoxShape.circle,
                                      ),
                                      child: const Icon(
                                        Icons.close,
                                        color: Colors.white,
                                        size: 14,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                        ..._newMedia.asMap().entries.map((entry) {
                          final index = entry.key;
                          final file = entry.value;
                          return Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: Stack(
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(10),
                                  child: Image.file(
                                    File(file.path),
                                    width: 120,
                                    height: 120,
                                    fit: BoxFit.cover,
                                  ),
                                ),
                                Positioned(
                                  right: 4,
                                  top: 4,
                                  child: InkWell(
                                    onTap: () {
                                      setState(() {
                                        _newMedia.removeAt(index);
                                      });
                                    },
                                    borderRadius: BorderRadius.circular(16),
                                    child: Container(
                                      padding: const EdgeInsets.all(4),
                                      decoration: BoxDecoration(
                                        color: Colors.black.withValues(
                                          alpha: 0.6,
                                        ),
                                        shape: BoxShape.circle,
                                      ),
                                      child: const Icon(
                                        Icons.close,
                                        color: Colors.white,
                                        size: 14,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _pickImages,
                  icon: const Icon(Icons.add_photo_alternate_outlined),
                  label: Text(l.pickImages),
                ),
                if (_dynamicDefs.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Text(
                    l.additionalDetails,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ..._dynamicDefs.map((def) => _buildDynamicField(def, l)),
                ],
                const SizedBox(height: 22),
                ElevatedButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: _saving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.save_outlined),
                  label: Text(l.save),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDynamicField(Map<String, dynamic> def, S l) {
    final key = def['key']?.toString() ?? '';
    final label = def['label']?.toString() ?? key;
    final valueType = def['value_type']?.toString() ?? 'string';
    final required = def['required'] == true;
    final options =
        (def['options'] as List?)?.map((item) => item.toString()).toList() ??
        const <String>[];

    if (valueType == 'boolean') {
      final selected = _dynamicDiscreteValues[key] == true;
      return SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: Text(label),
        subtitle: required ? Text(l.requiredField) : null,
        value: selected,
        onChanged: (value) {
          setState(() {
            _dynamicDiscreteValues[key] = value;
          });
        },
      );
    }

    if (options.isNotEmpty) {
      final selected = _dynamicDiscreteValues[key]?.toString();
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: DropdownButtonFormField<String>(
          initialValue: selected != null && options.contains(selected)
              ? selected
              : null,
          decoration: InputDecoration(labelText: required ? '$label *' : label),
          items: options
              .map(
                (value) =>
                    DropdownMenuItem<String>(value: value, child: Text(value)),
              )
              .toList(),
          onChanged: (value) {
            setState(() {
              _dynamicDiscreteValues[key] = value;
            });
          },
        ),
      );
    }

    final controller = _dynamicTextControllers.putIfAbsent(
      key,
      TextEditingController.new,
    );
    final keyboardType = (valueType == 'integer' || valueType == 'number')
        ? const TextInputType.numberWithOptions(decimal: true)
        : TextInputType.text;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        decoration: InputDecoration(labelText: required ? '$label *' : label),
      ),
    );
  }
}

class _MapPickerSheet extends StatefulWidget {
  const _MapPickerSheet({
    required this.initialLatitude,
    required this.initialLongitude,
    required this.initialAddressLabel,
  });

  final double? initialLatitude;
  final double? initialLongitude;
  final String? initialAddressLabel;

  @override
  State<_MapPickerSheet> createState() => _MapPickerSheetState();
}

class _MapPickerSheetState extends State<_MapPickerSheet> {
  static const _defaultCenter = LatLng(42.8746, 74.5698);

  late LatLng _selectedPoint;
  String? _addressLabel;
  bool _resolving = false;

  @override
  void initState() {
    super.initState();
    _selectedPoint =
        (widget.initialLatitude != null && widget.initialLongitude != null)
        ? LatLng(widget.initialLatitude!, widget.initialLongitude!)
        : _defaultCenter;
    _addressLabel = widget.initialAddressLabel;
    _resolveAddress(_selectedPoint);
  }

  Future<void> _resolveAddress(LatLng point) async {
    setState(() {
      _resolving = true;
    });

    try {
      final locale = Localizations.localeOf(context).languageCode;
      final dio = Dio(
        BaseOptions(
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 10),
          headers: const {'User-Agent': 'KMMarketplaceMobile/1.0'},
        ),
      );

      final response = await dio.get(
        'https://nominatim.openstreetmap.org/reverse',
        queryParameters: {
          'format': 'jsonv2',
          'lat': point.latitude.toStringAsFixed(6),
          'lon': point.longitude.toStringAsFixed(6),
          'accept-language': locale,
        },
      );

      final data = response.data;
      final label = (data is Map<String, dynamic>)
          ? data['display_name']?.toString()
          : null;

      setState(() {
        _addressLabel = (label != null && label.trim().isNotEmpty)
            ? label.trim()
            : '${point.latitude.toStringAsFixed(6)}, ${point.longitude.toStringAsFixed(6)}';
      });
    } catch (_) {
      setState(() {
        _addressLabel =
            '${point.latitude.toStringAsFixed(6)}, ${point.longitude.toStringAsFixed(6)}';
      });
    } finally {
      if (mounted) {
        setState(() {
          _resolving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return SizedBox(
      height: MediaQuery.of(context).size.height * 0.85,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 6, 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    l.setLocation,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
          Expanded(
            child: FlutterMap(
              options: MapOptions(
                initialCenter: _selectedPoint,
                initialZoom: 14,
                onTap: (tapPosition, point) {
                  setState(() {
                    _selectedPoint = point;
                  });
                  _resolveAddress(point);
                },
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'kg.demo.km_marketplace',
                ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _selectedPoint,
                      width: 42,
                      height: 42,
                      child: const Icon(
                        Icons.location_pin,
                        color: AppTheme.accent,
                        size: 42,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: const BoxDecoration(
              color: AppTheme.bgSurface,
              border: Border(top: BorderSide(color: AppTheme.border)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _resolving
                      ? l.loading
                      : (_addressLabel ?? l.selectPointOnMap),
                  style: const TextStyle(
                    color: AppTheme.textSubtle,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: Text(l.cancel),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () {
                          Navigator.of(context).pop(
                            _MapSelection(
                              latitude: _selectedPoint.latitude,
                              longitude: _selectedPoint.longitude,
                              addressLabel: _addressLabel,
                            ),
                          );
                        },
                        child: Text(l.apply),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MapSelection {
  const _MapSelection({
    required this.latitude,
    required this.longitude,
    required this.addressLabel,
  });

  final double latitude;
  final double longitude;
  final String? addressLabel;
}
